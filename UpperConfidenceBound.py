import logging
from abc import (
    ABC,
    abstractmethod,
)
from collections import defaultdict
from typing import List, Optional
from uuid import uuid4

import numpy as np
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class Bandit:
    def __init__(self, m: float, lower_bound: float = None, upper_bound: float = None, sigma=1):
        """
        Simulates bandit.
        Args:
            m (float): True mean.
            lower_bound (float): Lower bound for rewards.
            upper_bound (float): Upper bound for rewards.
        """

        self.m = m
        self.sigma = sigma
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.id = uuid4()

    def pull(self):
        """
        Simulate pulling the arm of the bandit.
        Normal distribution with mu = self.m and sigma = np.sigma. If lower_bound or upper_bound are defined then the
        distribution will be truncated.
        """
        n = 10
        possible_rewards = self.sigma * np.random.randn(n) + self.m

        allowed = np.array([True] * n)
        if self.lower_bound is not None:
            allowed = possible_rewards >= self.lower_bound
        if self.upper_bound is not None:
            allowed *= possible_rewards <= self.upper_bound

        return possible_rewards[allowed][0]


class BernoulliBandit:
    def __init__(self, p: float):
        """
        Simulates bandit.
        Args:
            p: Probability of success.
        """
        self.p = p
        self.id = uuid4()

    def pull(self):
        """
        Simulate pulling the arm of the bandit.
        """
        return np.random.binomial(1, self.p, size=1)[0]


class NoBanditsError(Exception):
    ...


class BanditRewardsLog:
    def __init__(self):
        self.total_actions = 0
        self.total_rewards = 0
        self.all_rewards = []
        self.record = defaultdict(lambda: dict(actions=0, reward=0, reward_squared=0))

    def record_action(self, bandit, reward):
        self.total_actions += 1
        self.total_rewards += reward
        self.all_rewards.append(reward)
        self.record[bandit.id]['actions'] += 1
        self.record[bandit.id]['reward'] += reward
        self.record[bandit.id]['reward_squared'] += reward ** 2

    def __getitem__(self, bandit):
        return self.record[bandit.id]


class Agent(ABC):
    def __init__(self):
        self.rewards_log = BanditRewardsLog()
        self._bandits = None

    @property
    def bandits(self) -> List[Bandit]:
        if not self._bandits:
            raise NoBanditsError()
        return self._bandits

    @bandits.setter
    def bandits(self, val: List[Bandit]):
        self._bandits = val

    @abstractmethod
    def take_action(self):
        ...

    def take_actions(self, n: int):
        for _ in range(n):
            self.take_action()


class EpsilonGreedyAgent(Agent):
    def __init__(self, epsilon: float = None):
        '''
        If epsilon=None it defaults to epsilon = 1 / #actions.
        '''
        super().__init__()
        self.epsilon = epsilon

    def _get_random_bandit(self) -> Bandit:
        return np.random.choice(self.bandits)

    def _get_current_best_bandit(self) -> Bandit:
        estimates = []
        for bandit in self.bandits:
            bandit_record = self.rewards_log[bandit]
            if not bandit_record['actions']:
                estimates.append(0)
            else:
                estimates.append(bandit_record['reward'] / bandit_record['actions'])

        return self.bandits[np.argmax(estimates)]

    def _choose_bandit(self) -> Bandit:
        epsilon = self.epsilon or 1 / (1 + self.rewards_log.total_actions)

        p = np.random.uniform(0, 1, 1)
        if p < epsilon:
            bandit = self._get_random_bandit()
        else:
            bandit = self._get_current_best_bandit()

        return bandit

    def take_action(self):
        current_bandit = self._choose_bandit()
        reward = current_bandit.pull()
        self.rewards_log.record_action(current_bandit, reward)
        return reward

    def __repr__(self):
        return 'EpsilonGreedyAgent(epsilon={})'.format(self.epsilon)


class UCBAgent(Agent):
    def __init__(self):
        super().__init__()
        self.initialised = False

    @abstractmethod
    def initialise(self):
        ...

    @abstractmethod
    def calculate_bandit_index(self, bandit):
        ...

    def _get_current_best_bandit(self) -> Bandit:
        estimates = [self.calculate_bandit_index(bandit) for bandit in self.bandits]
        return self.bandits[np.argmax(estimates)]

    def take_action(self):
        if not self.initialised:
            raise Exception('Initialisation step needs to be executed first.')

        current_bandit = self._get_current_best_bandit()
        reward = current_bandit.pull()
        self.rewards_log.record_action(current_bandit, reward)
        return reward


class UCB1Agent(UCBAgent):
    def initialise(self):
        if self.initialised:
            logger.info('Initialisation step has been executed before.')
            return

        for bandit in self.bandits:
            reward = bandit.pull()
            self.rewards_log.record_action(bandit, reward)
        self.initialised = True

    def calculate_bandit_index(self, bandit):
        '''
        Sample Mean + √(2logN / n)
        '''
        bandit_record = self.rewards_log[bandit]
        sample_mean = bandit_record['reward'] / bandit_record['actions']
        c = np.sqrt(2 * np.log(self.rewards_log.total_actions) / bandit_record['actions'])
        return sample_mean + c

    def __repr__(self):
        return 'UCB1()'


class UCB1TunedAgent(UCBAgent):
    def initialise(self):
        if self.initialised:
            logger.info('Initialisation step has been executed before.')
            return

        for bandit in self.bandits:
            reward = bandit.pull()
            self.rewards_log.record_action(bandit, reward)
        self.initialised = True

    def calculate_bandit_index(self, bandit):
        '''
        C = √( (logN / n) x min(1/4, V(n)) )
        where V(n) is an upper confidence bound on the variance of the bandit, i.e.
        V(n) = Σ(x_i² / n) - (Σ (x_i / n))² + √(2log(N) / n)
        '''
        bandit_record = self.rewards_log[bandit]
        n = bandit_record['actions']
        sample_mean = bandit_record['reward'] / n

        variance_bound = bandit_record['reward_squared'] / n - sample_mean ** 2
        variance_bound += np.sqrt(2 * np.log(self.rewards_log.total_actions) / n)

        c = np.sqrt(np.min([variance_bound, 1 / 4]) * np.log(self.rewards_log.total_actions) / n)
        return sample_mean + c

    def __repr__(self):
        return 'UCB1Tuned()'


class UCB1NormalAgent(UCBAgent):
    def initialise(self):
        if self.initialised:
            logger.info('Initialisation step has been executed before.')
            return

        for bandit in self.bandits:
            for _ in range(2):
                reward = bandit.pull()
                self.rewards_log.record_action(bandit, reward)

        self.initialised = True

    def calculate_bandit_index(self, bandit):
        '''
        Calculates the upper confidence index Sample Mean + C where C = √( 16 SV(n) log(N - 1) / n ) and the sample
        variance is
            SV(n) = ( Σ x_i² - n (Σ x_i / n)² ) / (n - 1)
        '''
        bandit_record = self.rewards_log[bandit]
        n = bandit_record['actions']

        sample_mean = bandit_record['reward'] / n
        sample_variance = (bandit_record['reward_squared'] - n * sample_mean ** 2) / (n - 1)
        c = np.sqrt(16 * sample_variance * np.log(self.rewards_log.total_actions - 1) / n)

        return sample_mean + c

    def _get_bandit_with_insufficient_data(self) -> Optional[Bandit]:
        res = []
        for bandit in self.bandits:
            bandit_record = self.rewards_log[bandit]
            if bandit_record['actions'] < np.max([3, np.ceil(8 * np.log(self.rewards_log.total_actions))]):
                res.append(bandit)

        if res:
            return np.random.choice(res)
        return None

    def _get_current_best_bandit(self) -> Bandit:
        estimates = [self.calculate_bandit_index(bandit) for bandit in self.bandits]
        return self.bandits[np.argmax(estimates)]

    def take_action(self):
        if not self.initialised:
            raise Exception('Initialisation step needs to be executed first.')

        current_bandit = self._get_bandit_with_insufficient_data()
        if not current_bandit:
            current_bandit = self._get_current_best_bandit()
        reward = current_bandit.pull()
        self.rewards_log.record_action(current_bandit, reward)
        return reward

    def __repr__(self):
        return 'UCB1Normal()'


def compare_agents(
        agents: List[Agent],
        bandits: List[Bandit],
        iterations: int,
        show_plot=True,
):
    for agent in agents:
        logger.info("Running for agent = %s", agent)
        agent.bandits = bandits
        if isinstance(agent, UCBAgent):
            agent.initialise()

        N = iterations - agent.rewards_log.total_actions
        agent.take_actions(N)
        if show_plot:
            cumulative_rewards = np.cumsum(
                agent.rewards_log.all_rewards,
            )
            plt.plot(cumulative_rewards, label=str(agent))

    if show_plot:
        plt.xlabel("iteration")
        plt.ylabel("total rewards")
        plt.legend(loc='upper left', bbox_to_anchor=(1, 0.5))
        plt.show()


def get_agents():
    agents = [
        EpsilonGreedyAgent(),
        UCB1Agent(),
        UCB1TunedAgent(),
        UCB1NormalAgent(),
    ]
    return agents


def run_comparison_ucb(bandits):
    win_count = [0, 0, 0, 0]

    for _ in range(1000):
        agents = get_agents()
        iterations = 1000
        compare_agents(agents, bandits, iterations, show_plot=False)

        rewards = [
            agent.rewards_log.total_rewards
            for agent in agents
        ]
        win_count[np.argmax(rewards)] += 1

    return win_count


if __name__ == '__main__':
    probs = [0.6, 0.7, 0.8, 0.9]
    bernoulli_bandits = [BernoulliBandit(p) for p in probs]
    agents = get_agents()
    compare_agents(agents, bernoulli_bandits, 1000, show_plot=True)
    run_comparison_ucb(bernoulli_bandits)
    means = [3, 5, 7, 9]
    normal_bandits = [Bandit(m=m, sigma=1) for m in means]
    compare_agents(agents, bernoulli_bandits, 1000, show_plot=True)
    run_comparison_ucb(bernoulli_bandits)
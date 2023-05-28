import numpy as np
import pprint
import sys
if "../" not in sys.path:
    sys.path.append("../")
from lib.envs.gridworld import GridworldEnv

def policy_eval(policy, env, discount_factor=1.0, theta=0.00001):
    """
  Evaluate a policy given an environment and a full description of the environment's dynamics.

  Args:
      policy: [S, A] shaped matrix representing the policy.
      env: OpenAI env. env.P represents the transition probabilities of the environment.
          env.P[s][a] is a list of transition tuples (prob, next_state, reward, done).
          env.nS is a number of states in the environment.
          env.nA is a number of actions in the environment.
      theta: We stop evaluation once our value function change is less than theta for all states.
      discount_factor: Gamma discount factor.

  Returns:
      Vector of length env.nS representing the value function.
  """
    # Start with a random (all 0) value function
    V = np.zeros(env.nS)
    while True:
        delta = 0
        # For each state, perform a "full backup"
        for s in range(env.nS):
            v = 0
            # Look at the possible next actions
            for a, action_prob in enumerate(policy[s]):
                # For each action, look at the possible next states...
                for prob, next_state, reward, done in env.P[s][a]:
                    # Calculate the expected value.
                    v += action_prob * prob * (reward + discount_factor * V[next_state])
            # How much our value function changed (across any states)
            delta = max(delta, np.abs(v - V[s]))
            V[s] = v
        # Stop evaluating once our value function change is below a threshold
        if delta < theta:
            break
    return np.array(V)


if __name__ == '__main__':
    shape = (4, 4)
    env = GridworldEnv(shape=shape)

    random_policy = np.ones([env.nS, env.nA]) / env.nA
    #print(random_policy)
    v = policy_eval(random_policy, env)

    print("Value Function:")
    print(v)
    print("")

    print(shape)
    print("Reshaped Grid Value Function:")
    print(v.reshape(shape))
    print("")

from agent import this_works

# Checks that the imports and connections
def checkEverything():
  print(f'{this_works('the agent')}')

# autodev run --ticket tickets/T-001.json --repo ./target-app
def run():
  checkEverything()

run()

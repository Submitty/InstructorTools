import json
import os
import argparse

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("input_file", help="The path to a valid Submitty configuration file.")
  args = parser.parse_args()

  try:
    with open(args.input_file, 'r') as infile:
      config_data = json.load(infile)
  except Exception as e:
    print("Your input file was not parsable. Did you leave the comments in it?")
    print("If you did, please instead pass in a 'complete_config', found at ")
    print("/var/local/submitty/courses/YOUR_SEMESTER/YOUR_COURSE/config/complete_config/complete_config_YOUR_GRADEABLE_NAME.json")

  if 'resource_limits' in config_data:
    default_testcase_time = config_data['resource_limits'].get('RLIMIT_CPU', 10)
  else:
    default_testcase_time = 10

  upper_bound = 0
  delayed_time = 0
  CPU_WALL_CLOCK_BUFFER = 10
  i = 0
  for testcase in config_data['testcases']:
    print('Testcase {0}: {1}'.format(i, testcase['title']))
    print('{0}'.format(testcase.get('type', 'Standard Testcase')))

    if 'resource_limits' in testcase:
      testcase_time = testcase['resource_limits'].get('RLIMIT_CPU', default_testcase_time)
    else:
      testcase_time = default_testcase_time

    delay_time = 0
    in_between_time = 0
    for action_type in ['actions', 'dispatcher_actions']:
      if action_type in testcase:
        for action in testcase[action_type]:
          if action['action'] == 'delay':
            delay_time += action['seconds']
          in_between_time += .1

    print('Max Allowed Time: {0} Sec ({1} Sec RLIMIT_CPU + {2} Sec Wall Clock Buffer)'.format(testcase_time + CPU_WALL_CLOCK_BUFFER, testcase_time, CPU_WALL_CLOCK_BUFFER))
    if delay_time > 0:
      print('Total Delays: {0:.2f} Sec'.format(delay_time))
    if in_between_time > 0:
      print('Action Pad Time: {0:.2f} Sec'.format(in_between_time))

    upper_bound += testcase_time + CPU_WALL_CLOCK_BUFFER
    delayed_time += delay_time + in_between_time
    print()
  print('-------------------------------------------------------------------')
  print('Maximum Possible Runtime: {0} Seconds'.format(upper_bound))
  if delayed_time > 0:
    print('Total Delay Time: {0} Seconds'.format(delayed_time))
  if config_data['required_capabilities'] != 'default':
    print('* It looks like your assignment is using non-default required capabilities. Is it being shipped? If so, there could be a small amount of additional delay.')

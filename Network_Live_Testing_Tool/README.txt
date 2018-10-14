This tool is meant to help instructors create docker networks for use in live 
testing networked student applications.

For information about the script and its arguments please run the script with the --help option.

The config json should contain an outer "testcases" list and an inner list of "container" dictionaries.
The specification of the container dictionary mirrors that used in submitty.
The config json should NOT include comments.
By default the first testcase is used to generate networks. You may optionally select another testcase.
Likely the command used will be /bin/bash so that you are dropped into a bash shell.

CONFIG_JSON example:

{
  "testcases" : [
    {
      "containers" : [
        {
          "container_name" : "container_a",
          "container_image" : "submittyrpi/csci4510:combined",
          "commands" : ["/bin/bash"]
        },
        {
          "container_name" : "container_b",
          "container_image" : "submittyrpi/csci4510:combined",
          "commands" : ["/bin/bash"]
        },
        {
          "container_name" : "container_c",
          "container_image" : "submittyrpi/csci4510:combined",
          "commands" : ["/bin/bash"]
        },
        {
          "container_name" : "container_d",
          "container_image" : "submittyrpi/csci4510:combined",
          "commands" : ["/bin/bash"]
        }
      ]
    }
  ]
}

CLEANUP:
After you finish evaluating a student's code, you will need to clean up your network.
This is done in three steps:
  1. stop the running containers.
  2. rm the stopped containers
  3. rm the created network. 

EXAMPLE CLEANUP SCRIPT:
#!/bin/bash

docker container rm -f container_a
docker container rm -f container_b
docker container rm -f container_c
docker container rm -f container_d

docker network rm routerless_network
import subprocess
import string
import zipfile
import traceback
import csv
import sys
import os
import shutil
import json
import argparse

class container_info_object:
  def __init__(self, untrusted_name, container_name, container_image, outgoing_connections, 
                                            command, parent_output_folder, mounted_directory):
    self.name = container_name
    self.image = container_image
    self.outgoing_connections = outgoing_connections
    self.command = command
    self.parent_output_folder = parent_output_folder
    self.mounted_directory = mounted_directory
    self.c_id = None

    if untrusted_name == None:
      self.untrusted_name = container_name
    else:
      self.untrusted_name = "{0}_{1}".format(untrusted_name, container_name)
      

  #Launch a single docker.
  def create_container(self):
    #TODO error handling.
    # print('docker create -i --network none -v {0}:{0} -w {0} --name {1} {2}'.format(
    #       self.mounted_directory, self.untrusted_name, os.path.join(self.mounted_directory, self.command)))
    c_id = subprocess.check_output(['docker', 'create', '-i', '-t', '--network', 'none',
                                   '-v', self.mounted_directory + ':' + self.mounted_directory,
                                   '-w', self.mounted_directory,
                                   '--name', self.untrusted_name,
                                   self.image,
                                   #The command to be run.
                                   os.path.join(self.mounted_directory, self.command)
                                   ]).decode('utf8').strip()

    self.c_id = c_id

  def cleanup(self):
    if self.c_id != None:
      subprocess.call(['docker', 'container', 'rm', '-f', self.c_id])
      # print("docker stop -f {0}".format(self.c_id))
      # print("docker rm -f {0}".format(self.c_id))

  def create_mounted_directory(self):
    if self.parent_output_folder != self.mounted_directory:
      os.makedirs(self.mounted_directory)

  def print_startup(self):
    print('docker start -i --attach {0}'.format(self.untrusted_name))


# copy the files & directories from source to target
# it will create directories as needed
# it's ok if the target directory or subdirectories already exist
# it will overwrite files with the same name if they exist
def copy_contents_into(source,target):
  if not os.path.isdir(target):
    raise RuntimeError("ERROR: the target directory does not exist '", target, "'")
  if os.path.isdir(source):
    for item in os.listdir(source):
      if os.path.isdir(os.path.join(source,item)):
        if os.path.isdir(os.path.join(target,item)):
          # recurse
          copy_contents_into(os.path.join(source,item),os.path.join(target,item))
        elif os.path.isfile(os.path.join(target,item)):
          raise RuntimeError("ERROR: the target subpath is a file not a directory '", os.path.join(target,item), "'")
        else:
          # copy entire subtree
          shutil.copytree(os.path.join(source,item),os.path.join(target,item))
      else:
        if os.path.exists(os.path.join(target,item)):
          os.remove(os.path.join(target,item))
        try:
          shutil.copy(os.path.join(source,item),target)
        except:
          raise RuntimeError("ERROR COPYING FILE: " +  os.path.join(source,item) + " -> " + os.path.join(target,item))

def create_container_objects(testcase, use_router, which_untrusted, output_folder):
  container_info_objects = {}
  instructor_container_specification = testcase['containers']

  for container_spec in instructor_container_specification:
    # Get the name, image, and outgoing_connections out of the instructor specification, filling in defaults if necessary.
    # Container name will always be set, and is populated by the complete config if not specified by the instructor
    container_name  = container_spec.get('container_name', None)
    if container_name is None:
      raise Exception("ERROR: Please name all of your containers.")
   
    container_image = container_spec.get('container_image', None)
    if container_image is None:
      raise Exception("ERROR: Please specify a container image.")
    
    outgoing_connections  = container_spec.get('outgoing_connections', [])

    commands = container_spec.get('commands', None)

    if type(commands) is list:
      if len(commands) > 1 or len(commands) == 0:
        raise Exception("ERROR: Your containers much each have a single command.")
      else:
        command = commands[0]
    elif commands is None:
      raise Exception("ERROR: Your containers much each have a single command.")
    
    mounted_directory = os.path.join(output_folder, container_name) if len(instructor_container_specification) > 1 else output_folder

    c = container_info_object(which_untrusted, container_name, container_image, outgoing_connections, command, output_folder, mounted_directory)

    container_info_objects[container_name] = c
  # if len(container_info) > 1 and 'router' not in container_info and use_router:
  #   container_info['router'] = container_info_element("ubuntu:custom", [])

  return container_info_objects

def setup_folder_for_user_deployment(container_obj, input_directory, submissions_directory, student_name, active_version):
  #TODO: pre-commands may eventually wipe the following logic out.
  #copy the required files to the test directory
  student_code_directory = os.path.join(submissions_directory,"submissions",student_name,str(active_version))
  copy_contents_into(student_code_directory, container_obj.mounted_directory)
  student_checkout_directory = os.path.join(submissions_directory,"checkout",student_name,str(active_version))
  if os.path.exists(student_checkout_directory):
      copy_contents_into(student_checkout_directory, container_obj.mounted_directory)

  copy_contents_into(input_directory,container_obj.mounted_directory)

def network_containers(container_info,test_input_folder,which_untrusted, use_router,single_port_per_container):
  if len(container_info) <= 1:
    return

  #remove all containers from the none network
  for name, c_object in sorted(container_info.items()):
    subprocess.check_output(['docker', 'network','disconnect', 'none', c_object.c_id]).decode('utf8').strip()
    #print('docker network disconnect none {0}'.format(c_object.c_id))

  network_name = network_containers_routerless(container_info,which_untrusted)

  create_knownhosts_txt(container_info,test_input_folder,single_port_per_container)

  return network_name

def network_containers_routerless(container_info,which_untrusted):
  if which_untrusted is None:
    network_name = "routerless_network"
  else:
    network_name = '{0}_routerless_network'.format(which_untrusted)

  #create the global network
  subprocess.check_output(['docker', 'network', 'create', '--internal', '--driver', 'bridge', network_name]).decode('utf8').strip()
  #print("docker network create --internal --driver bridge {0}".format(network_name))

  for name, c_object in sorted(container_info.items()):
      print('adding {0} to network {1}'.format(name,network_name))
      #print('docker network connect --alias {0} {1} {2}'.format(c_object.name, network_name, c_object.untrusted_name))
      if c_object.untrusted_name == c_object.name:
        subprocess.check_output(['docker', 'network', 'connect', network_name, c_object.untrusted_name]).decode('utf8').strip()
      else:
        subprocess.check_output(['docker', 'network', 'connect', '--alias', c_object.name, network_name, c_object.untrusted_name]).decode('utf8').strip()
  return network_name

def create_knownhosts_txt(container_info,test_input_folder,single_port_per_container):
  tcp_connection_list = list()
  udp_connection_list = list()
  current_tcp_port = 9000
  current_udp_port = 15000

  for name, c_object in sorted(container_info.items()):
      if single_port_per_container:
          tcp_connection_list.append([name, current_tcp_port])
          udp_connection_list.append([name, current_udp_port])
          current_tcp_port += 1
          current_udp_port += 1  
      else:
          for connected_machine in c_object.outgoing_connections:
              if connected_machine == name:
                  continue

              tcp_connection_list.append([name, connected_machine,  current_tcp_port])
              udp_connection_list.append([name, connected_machine,  current_udp_port])
              current_tcp_port += 1
              current_udp_port += 1

  #writing complete knownhosts csvs to input directory
  knownhosts_location = os.path.join(test_input_folder, 'knownhosts_tcp.txt')
  with open(knownhosts_location, 'w') as outfile:
    for tup in tcp_connection_list:
      outfile.write(" ".join(map(str, tup)) + '\n')
      outfile.flush()

  knownhosts_location = os.path.join(test_input_folder, 'knownhosts_udp.txt')
  with open(knownhosts_location, 'w') as outfile:
    for tup in udp_connection_list:
      outfile.write(" ".join(map(str, tup)) + '\n')
      outfile.flush()


def create_containers(my_testcase, testcase_num, input_directory, output_directory, which_untrusted=None, submissions_directory=None, student_name=None, active_version=None):
  if 'type' in my_testcase:
    if my_testcase['type'] == 'FileCheck' or my_testcase['type'] == 'Compilation':
      raise Exception("ERROR: There is no network to be created for a compilation or filecheck testcase.")

  #make the tmp folder for this testcase.
  output_folder = os.path.join(output_directory, "test{:02}".format(testcase_num))

  if os.path.exists(output_folder):
    shutil.rmtree(output_folder)
  os.makedirs(output_folder)
  network_name = None
  try:
    # use_router = my_testcase['use_router']
    # if use_router:
    #   print("The router is not currently supported in this build. Please set use_router to false.")
    #   use_router = False
    use_router = False

    single_port_per_container = my_testcase.get('single_port_per_container', True)

    container_info = create_container_objects(my_testcase, use_router, which_untrusted, output_folder)

    for name, container_obj in container_info.items():
      container_obj.create_mounted_directory()
      print("Creating container {0}".format(container_obj.name))
      container_obj.create_container()

    network_name = network_containers(container_info,input_directory,which_untrusted,use_router,single_port_per_container)

    #Set up the mounted folders before any dockers start running in case large file transfer sizes cause delay.
    for name, obj in container_info.items():
      setup_folder_for_user_deployment(obj, input_directory, submissions_directory, student_name, active_version)
      #The containers are now ready to execute.
  except Exception as e:
    print('An error occurred when setting up your docker network:')
    traceback.print_exc()
    print()
    print("Removing all created containers. Please examine the provided stack trace and attempt to rectify the error before running again.")
    for name, container_obj in container_info.items():
      container_obj.cleanup()
    if network_name is not None:
      subprocess.call(['docker', 'network', 'rm', network_name])
    return None
  return container_info



if __name__ == '__main__':
  #I need path and student
  parser = argparse.ArgumentParser(description='This utility will help you to quickly deploy docker networks to test student assignment submissions',)
  parser.add_argument('config_path',  help="The path to the configuration json for this homework. See README for specification.", type=str)
  parser.add_argument('root_submission_path', help="The path to the folder containing the submissions directory.", type=str)
  parser.add_argument('output_path',  help="The FULL path to which you want to store result files.", type=str)
  parser.add_argument('student_id',   help="The id of the student submission to be graded.", type=str)
  parser.add_argument('--testcase_num', help="The testcase to be run (testcases start at 1)", type=int, default=1)
  parser.add_argument('--input_path',  '-i',  help="The path to the folder holding instructor provided files", type=str, default="input")

  args = parser.parse_args()
  config_path = args.config_path
  input_path = args.input_path
  submission_path = args.root_submission_path
  student_id = args.student_id
  testcase_num = args.testcase_num
  output_path = args.output_path

  output_path = os.path.join(output_path, student_id)

  if not os.path.exists(input_path):
    os.makedirs(input_path)

  try:
    with open(config_path, 'r') as infile:
      config = json.load(infile)
  except Exception as e:
    print("ERROR: Could not locate or open {0}".format(config_path))
    sys.exit(1)

  try:
    with open(os.path.join(submission_path,"submissions",student_id,'user_assignment_settings.json'), 'r') as infile:
      user_assignment_settings = json.load(infile)
  except Exception as e:
    print("Could not find the file {0}".format(os.path.join(submission_path,"submissions",student_id,'user_assignment_settings.json')))
    sys.exit(1)

  active_version = user_assignment_settings['active_version']
  print("{0}'s active version is {1}".format(student_id, active_version))

  try:
    my_testcase = config['testcases'][testcase_num-1]
  except Exception as e:
    print("ERROR: could not access testcase {0} in the testcases array in the configuration file.".format(testcase_num))


  network_objects = create_containers(my_testcase, testcase_num, input_path, output_path, which_untrusted=student_id, submissions_directory=submission_path, student_name=student_id, active_version=active_version)

  if network_objects is None:
    sys.exit(1)

  print("To run your containers, use the following commands:")
  print()
  for name, obj in network_objects.items():
    obj.print_startup()

  sys.exit(0)
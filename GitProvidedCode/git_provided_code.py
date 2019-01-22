#!/usr/bin/python


import argparse
import subprocess
import os
import sys
import shutil
import pathlib


def parse_args():
    """
    Parse the arguments for this script and return the namespace from argparse.
    """
    parser = argparse.ArgumentParser(description="Initialize student repos with instructor-provided code.")
    parser.add_argument("semester", type=str, help="semester, e.g., 's19'")
    parser.add_argument("course", type=str, help="course, e.g., 'csci1200'")
    parser.add_argument("repo", type=str, help="gradeable/repo name, e.g., 'hw1'")
    parser.add_argument("src_dir", type=str, help="provided source code directory/filename, e.g., '~/teaching/provided_code/hw1'")
    parser.add_argument("message", type=str, help="git commit message, e.g., 'initial code'")
    parser.add_argument("students", type=str, help="file containing student ids, e.g., '~/teaching/students.txt'")
    return parser.parse_args()


def main():
    """
    Main execution function
    """

    # parse the command line arguments
    args = parse_args()
    
    # minimal error checking
    if not os.path.exists(args.src_dir):
        raise SystemExit("ERROR: instructor source code directory does not exist: "+args.src_dir)

    # note the current directory
    current_directory = os.getcwd()

    # make a top level directory for the repo (if it doesn't already exist)
    repo_path = os.path.join (args.course, args.repo)
    os.makedirs(repo_path,exist_ok=True)

    # read the student files
    with open(args.students, 'r') as f:
        student_names = f.readlines()
        for student in student_names:
            os.chdir(current_directory)
            student = student.strip()
            if student == "":
                continue
            process_student(args,student)

            
def process_student(args,student):
    """
    Deal with the provided code for each student
    """
    
    print ("============================================\nPROCESS STUDENT "+student)

    # make directory and clone repo
    repo_path = os.path.join (args.course, args.repo)
    student_path = os.path.join (args.course, args.repo, student)
    print (student_path)

    # TODO: Could revise to skip this step and be more efficient and
    # use and update existing checkout (but this could be messy if
    # history was edited)
    shutil.rmtree(student_path,ignore_errors=True)

    url = "https://submitty.cs.rpi.edu/git/"+args.semester+"/"+args.course+"/"+args.repo+"/"+student
    
    success = subprocess.call (['git','clone',url,student_path])
    if not success == 0:
        print ("ERROR: git clone failed")
        return
        
    os.chdir (student_path)

    # do the master & provided repos exist?
    master_exists = subprocess.call(['git','show-ref','master'])
    provided_exists = subprocess.call(['git','show-ref','provided'])
    
    # go to the provided branch (create if doesn't exist)
    if provided_exists == 0:
        print(student," provided branch exists!")
        subprocess.call (['git','checkout','provided'])
    else:
        print(student," provided branch DOES NOT EXIST")
        subprocess.call (['git','checkout','-b','provided'])
    
    # add the files, and commit them TODO: Could revise to be more
    # efficient and not force delete and replace all the top level
    # files & directories (also this does not delete any dot files or
    # dot directories at the top level -- have to leave the .git
    # directory after all)
    subprocess.call (['rm','-rf','*'])
    subprocess.call (['rsync','--delete','-a',args.src_dir,'.'])
    subprocess.call (['git','add','--all'])
    subprocess.call (['git','commit','-m',args.message])
    subprocess.call (['git','push','origin','provided'])

    # if the master branch doesn't yet exist, put the provided code in
    # that branch too
    if master_exists == 0:
        print(student," master branch exists!")
    else:
        print(student," master branch DOES NOT EXIST")
        subprocess.call (['git','checkout','-b','master'])
        subprocess.call (['git','branch','--unset-upstream'])
        subprocess.call (['git','merge','provided'])
        subprocess.call (['git','push','origin','master'])

    print ("finished student "+student)
    

main()



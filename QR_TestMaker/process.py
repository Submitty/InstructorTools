#!/usr/bin/python3
'''
This example assumes that for a gradeable "test1_notes_page" using the test_notes_upload
or test_notes_upload_3page configurations, you have copied results/test1_notes_page/ from Submitty
to the path resultdir and submissions/test1_notes_page/ to the path submission_dir (needed to make 
sure we grab the active version).

It will extract a generated PDF from each student's directory and put it in the directory
specified by targetdir.
'''

import subprocess
import glob
import os
import json
import shutil

submissiondir = "submissions_test1_notes_page/"
resultdir = "results_test1_notes_page/"
targetdir = "student_notes/"

if not os.path.isdir(targetdir):
	os.mkdir(targetdir)

for x in os.listdir(submissiondir):

    with open (submissiondir+"/"+x+"/user_assignment_settings.json") as uad:
        data = json.load(uad)
        version = data["active_version"]
        my_dir = resultdir+"/"+x+"/"+str(version)
        if version==0:
            print(x + " does not have an active version, skipping")
            continue
    pdfpath = os.path.join(my_dir,"details","test02","test_template.pdf")
    if os.path.isfile(pdfpath):
        shutil.copyfile(pdfpath,"student_notes/"+x+".pdf")
    else:
        print("Failed to extract a PDF for user: {}".format(x))

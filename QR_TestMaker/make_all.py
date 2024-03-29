#!/usr/bin/env python3

import subprocess
import glob
import os
import PyPDF2
import qrcode
import sys
from PIL import Image
import pathlib


# constants (should eventually turn these into command line arguments)
special_word = "f2099_csci1200_test_"
notes_dir = "student_notes"
qr_dir = "qr"
seating_file = "test_seating.txt"
blank_data = "blank"
debug_mode = False
staff_section = "STAFF" #Name of a section to skip, useful for TAs/staff in a class            


# takes the test template file, and overlays the custom information on
# the file, and attaches the students cribsheet (if provided)
def make_custom_pdf(blank_test_file,cribsheet_file,overlay_file,custom_file):
    print (custom_file)
    # overlay custom infomation on the cover page
    output = PyPDF2.PdfWriter()
    main_handout = PyPDF2.PdfReader(blank_test_file)
    if cribsheet_file != "":
        cribsheet = PyPDF2.PdfReader(cribsheet_file, strict=False)
    overlay = PyPDF2.PdfReader(overlay_file, strict=False)
    try:
        my_cover = main_handout.pages[0]
        my_cover.merge_page(overlay.pages[0])
        output.add_page(my_cover)
    except IndexError:
        print("Failed to get cover page for exam")
        return False
    # for every other page, we just put the name in the upper right corner
    numpages = len(main_handout.pages)
    try:
        for i in range(1,numpages):
            page = main_handout.pages[i]
            page.merge_page(overlay.pages[1])
            output.add_page(page)
    except IndexError:
        print("Failed to get page",i,"from exam")
        return False
    # and attach the cribsheet
    if cribsheet_file != "":
        try:
            crib1 = cribsheet.pages[2]
            crib1.merge_page(overlay.pages[1])
            crib2 = cribsheet.pages[3]
            crib2.merge_page(overlay.pages[1])
            output.add_page(crib1)
            output.add_page(crib2)
        except IndexError:
            print("Failed to get a page of cribsheet file (should be pages 3 and 4 of)",cribsheet_file)
            return False
    outputStream = open(custom_file,"wb")
    try:
        output.write(outputStream)
    except PyPDF2.utils.PdfReadError:
        print("^^^Failed to write PDF, probably due to student corruption. Try opening",custom_file,"in a PDF reader")
        return False
    return True

# BEFORE RE-GENERATING...  CLEAN UP ALL OLD FILES
def cleanup():
    files = glob.glob("to_print/*")
    subprocess.call(['rm','-rf']+files)
    pathlib.Path(notes_dir+"/").mkdir(parents=True,exist_ok=True)
    pathlib.Path(qr_dir+"/").mkdir(parents=True,exist_ok=True)
    

# generated file not used anymore 
def build_default_notes():
    if debug_mode:
        subprocess.call(['pdflatex','nonotes.tex'])
    else:
        subprocess.call(['pdflatex','nonotes.tex'], stdout=open(os.devnull, 'wb'))
    subprocess.call(['cp','nonotes.pdf',notes_dir])


# run latex to produce the blank test template...
def build_exam():
    if debug_mode:
        subprocess.call(['rm', '-rf', 'test_template.pdf'])
        subprocess.call(['pdflatex', 'test_template.tex'])
    else:
        subprocess.call(['rm', '-rf', 'test_template.pdf'], stdout=open(os.devnull, 'wb'))
        subprocess.call(['pdflatex', 'test_template.tex'], stdout=open(os.devnull, 'wb'))

def make_all_exams():
    # loop over the seating file, making an exam for each of the rows/students
    with open(seating_file,"r") as seating:
        for line in seating:
            things=line.split()
            if len(things) < 3:
                continue
            username = things[2].replace('_',' ')
            studentnotes = username+".pdf"
            last = things[0].replace('_',' ')
            first = things[1].replace('_',' ')
            email = username + "@rpi.edu"
            if username=="N/A":
                username=""
                email=""
            if len(things) == 3:
                if os.path.isfile(notes_dir+"/"+studentnotes):
                    print ("==========WEIRD!  this student dropped but submitted notes",things[2])
                continue
            section = things[3].replace('_',' ')
            if section=="N/A":
                section=""
            if section == staff_section:
                continue
            if len(things) == 4:
                print ("============PROBABLE DROP "+things[2])
                if os.path.isfile(notes_dir+"/"+studentnotes):
                    print ("WEIRD!  this student probably dropped but submitted notes",things[2])
                continue
            if not len(things) >= 9:
                print ("==========SKIPPING      "+things[2])
                if os.path.isfile(notes_dir+"/"+studentnotes):
                    print ("==========WEIRD!  this skipped student submitted notes",things[2])
                continue
            note = ""
            for i in things[9:]:
                note += " "+i
            building = things[4].replace('_',' ')
            room = things[5].replace('_',' ')
            zone = things[6].replace('_',' ')
            row = things[7].replace('_',' ')
            row = row.replace('N/A','')
            seat = things[8].replace('_',' ')
            seat = seat.replace('N/A','')
            time = note.strip()
            if time=="N/A":
                time=""
            if not os.path.isfile(notes_dir+"/"+studentnotes):
                studentnotes = ""
            else:
                studentnotes = notes_dir+"/"+studentnotes
            if first=="N/A":
                first=""
            label = zone+"_"+row+"_"+seat
            if last=="N/A":
                last = label.replace('_',' ')
            if username=="":
                filename=label+'.pdf'
                data = special_word+label
            else:
                filename=label+"_"+username+'.pdf'
                data = special_word+username
            filename = filename.replace('N/A_','')

            # make the qr code
            qr = qrcode.QRCode(
                version = 1,
                #error_correction = qrcode.constants.ERROR_CORRECT_H, _L, _M, _Q, _H
                box_size = 10,
                border = 4,
            )
            qr.add_data(data)
            img = qr.make_image()
            img.save(qr_dir +"/"+ data + '.png') #can also be .bmp, .jpeg
            with open("student_variables.tex","w") as f:
                f.write ("\\newcommand{\\studentemail}{"+email+"}\n")
                f.write ("\\newcommand{\\studentfirstname}{"+first+"}\n")
                f.write ("\\newcommand{\\studentlastname}{"+last+"}\n")
                f.write ("\\newcommand{\\studentlabsection}{"+section+"}\n")
                f.write ("\\newcommand{\\studentroom}{"+building+" "+room+"}\n")
                f.write ("\\newcommand{\\studentzone}{"+zone+"}\n")
                f.write ("\\newcommand{\\studentrow}{"+row+"}\n")
                f.write ("\\newcommand{\\studentseat}{"+seat+"}\n")
                f.write ("\\newcommand{\\studenttime}{"+time+"}\n")
                f.write ("\\newcommand{\\studentnotespage}{"+studentnotes+"}\n")
                f.write ("\\newcommand{\\qrcode}{"+qr_dir+"/"+data+".png}\n")
                f.write ("\\def\\beginnone{\\iffalse}")
                if section=="":
                    f.write ("\\def\\beginzoneandname{\\iffalse}")
                    f.write ("\\def\\beginzoneonly{\\iftrue}")
                else:
                    f.write ("\\def\\beginzoneandname{\\iftrue}")
                    f.write ("\\def\\beginzoneonly{\\iffalse}")
            if debug_mode:
                subprocess.call(['pdflatex', 'overlay.tex'])
            else:
                subprocess.call(['pdflatex', 'overlay.tex'], stdout=open(os.devnull, 'wb'))

            if make_custom_pdf("test_template.pdf",studentnotes,"overlay.pdf",filename):
                subprocess.call(['mkdir', '-p', 'to_print/'+zone])
                subprocess.call(['mv',filename,'to_print/'+zone+'/'+filename])

        qr = qrcode.QRCode(
            version = None,
            error_correction = qrcode.constants.ERROR_CORRECT_H,
            box_size = 10,
            border = 4,
        )
        qr.add_data(blank_data)
        qr.make(fit=True)

        img = qr.make_image()
        img.save(qr_dir+'/' + blank_data + '.png') #can also be .bmp, .jpeg
        
        with open("student_variables.tex","w") as f:
            f.write ("\\newcommand{\\qrcode}{"+qr_dir+"/"+blank_data+".png}\n")
            f.write ("\\def\\beginnone{\\iftrue}")                
            f.write ("\\def\\beginzoneandname{\\iffalse}")
            f.write ("\\def\\beginzoneonly{\\iffalse}")

        if debug_mode:
            subprocess.call(['pdflatex', 'overlay.tex'])
        else:
            subprocess.call(['pdflatex', 'overlay.tex'], stdout=open(os.devnull, 'wb'))
            
        make_custom_pdf("test_template.pdf","","overlay.pdf","blank_test")
        
        subprocess.call(['mv',"blank_test",'to_print/blank_test.pdf'])
        
def main():
    cleanup()
    build_default_notes()
    build_exam()
    make_all_exams()


main()

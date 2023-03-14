import json
import time
import imghdr
import argparse
import getpass, requests, os, re
from pathlib import Path
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from datetime import datetime

##################################################################
# a few optional command line argument variables
parser = argparse.ArgumentParser(description='RPI SIS Photo and Registration Scraper')
parser.add_argument('--credentials_file', type=str, default="",
                    help='a file containing the user RIN and PIN')
parser.add_argument('--term_file', type=str, default="",
                    help='a file containing the term')
parser.add_argument('--ews_file', type=str, default="",
                    help='a file containing the course crn & student ids')
parser.add_argument('--headless', default=False, action="store_true",
                    help='run program without visual display')

args = parser.parse_args()


##################################################################
# Workaround for if pyopenssl is installed and we want weak keys
try:
    from urllib3.contrib import pyopenssl
    pyopenssl.extract_from_urllib3()
except ImportError:
    pass


##################################################################
# Login to SIS
def login():
    chrome_options = Options()
    # read credentials from (optional) file
    if len(args.credentials_file)>0 and os.path.isfile(args.credentials_file):
        with open(str(args.credentials_file),'r') as f:
            rin_id = f.readline().strip()
            pin_id = f.readline().strip()
    else:
        rin_id = input("RIN: ")
        pin_id = getpass.getpass("PIN: ")

    # By default we launch the display and allow visual debugging
    if args.headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")

    chrome_options.add_argument(r"--user-data-dir=/Users/cutler/Library/Application\ Support/Google/Chrome/Default")
    #C:\path\to\chrome\user\data") #e.g. C:\Users\You\AppData\Local\Google\Chrome\User Data
    #chrome_options.add_argument(r'--profile-directory=YourProfileDir') #e.g. Profile 3
    #chrome_options.add_argument(r'--profile-directory=YourProfileDir') #e.g. Profile 3


        
    # Just setting the default ciphers (for this session) to be weak DES/SHA for SIS compatibility
    # Be careful about navigating to any other sites...
    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'DES-CBC3-SHA:AES128-SHA:'+requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS
    driver = webdriver.Chrome(options=chrome_options)

    # open SIS
    driver.get('https://sis.rpi.edu/')

    count = 0
    while True:
        count += 1
        # Types in username & password in login page
        try:
            username_box = driver.find_element_by_id('username')
            break
        except:
            if count > 10:
                print ("ERROR: couldn't find username box")
                exit(0)
        # slight delay to allow page to load
        print ("wait a little longer for the page to load")
        time.sleep(1)
    username_box.send_keys(rin_id)
    try:
        password_box = driver.find_element_by_id('password')
    except:
        print ("ERROR: couldn't find password box")
        exit(0)

    password_box.send_keys(pin_id)

    time.sleep(2)

    try:
        # click login button
        login_button = driver.find_element_by_name("submit")
    except:
        print ("ERROR: couldn't find submit button")
        exit(0)

    print ("now we can click login button")
    login_button.click()

    time.sleep(2)

    while True:

        time.sleep(3)

        if "Rensselaer Self-Service Information System" in driver.page_source:
            print("success -- made it past duo page")
            break
        else:
            print("please complete duo authentication")

    print ("Continuing with processing...")
    success = True

    return driver, success


##################################################################
# Gets the session/term the user wants
def selectTerm(driver):
    # read term from (optional) file
    term = ""
    if len(str(args.term_file))>0 and os.path.isfile(str(args.term_file)):
        with open(str(args.term_file),'r') as f:
            term = f.readline().strip()

    # click Instructors & Advisors Menu
    driver.find_element_by_link_text('Instructor & Advisor Menu').click()

    # click Select a Semester or Summer Session
    driver.find_element_by_link_text('Select a Semester or Summer Session').click()

    # grab the list of available terms
    select_term = Select(driver.find_element_by_name('term'))
    options_term = select_term.options

    # loop (querying live user) until we have a valid term
    foundTerm = False
    while not foundTerm:
        # print the available sessions/terms
        if term == "":
            print("Here are the available Sessions/Terms:")
            for index in range(len(options_term)):
                print("[{0}] {1}".format(index,options_term[index].text))
            term = input("Select a term ( or Exit to terminate ): ")
        # if user does not wish to continue, exit
        if term.lower() == "exit":
            return term, False
        # loops through all the term options to see if there is a match
        for index in range(len(options_term)):
            if options_term[index].text == term or str(index) == term:
                select_term.select_by_index(index)
                foundTerm = True
                term = options_term[index].text
                break
        # if no match with any term options, print out that the term cannot be found
        if not foundTerm:
            print("Cannot find the term")
            term = ""

    # click submit button
    driver.find_element_by_xpath("//input[@value='Submit']").click()

    return term, True





##################################################################
# returns the class list of dictionaries of info collected about each student's img url, name, and email
def getStudentInfoFromCourse(driver, term):

    class_list = []

    # click Summary Class List & Electronic Warning System (EWS)
    driver.find_element_by_link_text('Summary Class List & Electronic Warning System (EWS)').click()

    try:
        current_record = driver.find_element_by_partial_link_text('Current Record Set')
        #print ("'Current Record Set' label found")
        try:
            first = driver.find_element_by_link_text('Current Record Set: 1 - 200')
            print ("1-200 found")
            getStudentInfoFromCourseHelper(driver,term, class_list)
            print ("1-200 finished")
            try:
                second = driver.find_element_by_partial_link_text('201 -')
                print ("201-?? found")
                second.click()
                getStudentInfoFromCourseHelper(driver,term, class_list)
                driver.back()
                print ("201-?? finished")
            except:
                print ("ERROR IN CURRENT RECORD COUNTING -- SECOND")
                return 0
        except:
            print ("ERROR IN CURRENT RECORD COUNTING -- FIRST")
            return 0
    except:
        #print ("'Current Record Set' label not found")
        getStudentInfoFromCourseHelper(driver,term, class_list)

    driver.back()
    driver.back()

    if class_list == 0:
        print ("Warning: this class size is 0")
    else:
        # Use the info collected and save the image with rcs id for term/course in current directory
        #saveImagesToFolder(term, class_list)
        print ("no images")
        
##################################################################
def addMajor(majors,degree,text):
    majors.append(degree + " / " + text)
    return majors


def addConcentrationToLastMajor(majors,text):
    majors[-1] = majors[-1] + " / " + text
    return majors


##################################################################
# returns the class list of dictionaries of info collected about each student's img url, name, and email
def getStudentInfoFromCourseHelper(driver, term, class_list):

    print("hit return")
    input()
    
    # check if class is size 0
    if len(driver.find_elements_by_class_name('errortext')) == 1:
        print("Error: Class size is 0!")
        return 0

    COURSENAMESTRING = driver.find_elements_by_class_name('datadisplaytable')[0].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')[0].find_elements_by_tag_name('th')[0].text

    COURSENAMESTRING_split = COURSENAMESTRING.split(' - ')
    if len(COURSENAMESTRING_split) < 2:
        print ("ERROR: course name formatting bug")
        return 0
    COURSENAME = ""
    for index in range(len(COURSENAMESTRING_split)-1):
        if index > 0:
            COURSENAME = COURSENAME + " - "
        COURSENAME = COURSENAME + COURSENAMESTRING_split[index]

    print ("COURSE NAME IS "+COURSENAME)

    if len(COURSENAMESTRING_split[-1]) != 12:
        print ("ERROR: course prefix / code bug")
        return 0
    COURSEPREFIX = COURSENAMESTRING_split[-1][0:4]
    COURSENUMBER = COURSENAMESTRING_split[-1][5:9]
    COURSESECTION = COURSENAMESTRING_split[-1][10:]

    CRNSTRING = driver.find_elements_by_class_name('datadisplaytable')[0].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')
    CRNSTRING = str(CRNSTRING[1].text)
    if CRNSTRING[0:5] == "CRN: ":
        CRNSTRING = CRNSTRING[5:]
    else:
        print ("ERROR: could not find CRN")
        return 0

    # find link for pic
    student_list = driver.find_elements_by_class_name('datadisplaytable')[2].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')

    # find which column is the "Student Name" column, since it isn't always the same column number
    student_headers = student_list[0].find_elements_by_tag_name('th')
    stu_col = -1
    id_col = -1
    for i in range(len(student_headers)):
        if student_headers[i].text == "Student Name":
            stu_col = i
        if student_headers[i].text == "ID":
            id_col = i

    if stu_col < 0:
        print("Error: Could not find a column labeled \"Student Name\"!")
        return 0

    if id_col < 0:
        print("Error: Could not find a column labeled \"ID\"!")
        return 0

    # NOTE: uncomment this line to help with debugging
    #print("Student column: " + str(stu_col))

    # loop through list of students to get image, name, and email
    # all info collected from for loop (img url, name, email) put into dict
    for s in range(1, len(student_list)):
        student_record = {}
        student = driver.find_elements_by_class_name('datadisplaytable')[2].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')[s]

        # NOTE: uncomment these line to help with debugging
        #print('Row Number: ' + str(s))
        #print('Row Length: ' + str(len(student.find_elements_by_tag_name('td'))))
        #print('Cell Value: ' + student.find_elements_by_tag_name('td')[stu_col].text)

        full_name_cell = student.find_elements_by_tag_name('td')[stu_col].text
        full_name_cell_split = full_name_cell.split(', ')
        # format of the full name appears to be one of:
        #    Smith, John X.             (with middle initial)
        #    Smith, John                (with no middle name/initial)
        #    Smith Jones, John Edward   (spaces in first & last name are ok)
        if len(full_name_cell_split) == 2:
            last_name = full_name_cell_split[0]
            first_name = full_name_cell_split[1]
            middle_name = ""
            first_name_length = len(first_name)
            if first_name_length > 3 and first_name[first_name_length-3] == ' ' and first_name[first_name_length-1] == '.':
                middle_name = first_name[first_name_length-2:]
                first_name = first_name[0:first_name_length-3]

        id_rin = student.find_elements_by_tag_name('td')[id_col].text

        try:
            student.find_elements_by_tag_name('td')[stu_col].find_element_by_class_name('fieldmediumtext').click()
        except:
            input()
            raise

        img_url = driver.current_url
        driver.get(img_url)

        # image, initalize to empty string
        student_record['img url'] = ""
        image_arr = driver.find_elements_by_tag_name('img')

        #do search through all <img> tags for first non-header-layout tag
        #have to skip 2 more <img> tags because they are transparent images
        for i in range(len(image_arr)):
            if image_arr[i].get_attribute('NAME') != "web_tab_corner_right":
                student_record['img url'] = image_arr[i+2].get_attribute('src')
                #Uncomment this line to print the image URLs we are attempting, useful for debugging
                #print("found non-match, +2 is " + student_record['img url'])
                break

        # name
        info_name = driver.find_elements_by_class_name('plaintable')[4].find_element_by_tag_name('tbody').find_element_by_tag_name('tr').find_elements_by_tag_name('td')[1].text

        name = info_name[16:]
        student_record['name'] = name
        student_record['rin'] = id_rin

        student_record['first_name'] = first_name
        student_record['middle_name'] = middle_name
        student_record['last_name'] = last_name

        student_record['course_name'] = COURSENAME
        student_record['course_number'] = COURSENUMBER
        student_record['course_prefix'] = COURSEPREFIX
        student_record['course_crn'] = CRNSTRING
        student_record['course_section'] = COURSESECTION

        student_record['term'] = term

        print("Gathering info for student: "+name)

        # email address
        driver.find_element_by_link_text('Student E-mail Address').click()
        if len(driver.find_elements_by_class_name('datadisplaytable')) == 1:
            emails = driver.find_element_by_class_name('datadisplaytable').find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')
            for i in range(len(emails)):
                if emails[i].text == "Campus Student Email Address":
                    email = emails[i+1].find_element_by_tag_name('td').text
                    student_record['email'] = email
                    student_record['rcs'] = email[0:len(email)-8]
                    break
        driver.back()

        degree = "UNKNOWN"
        majors = []

        # undergraduate major
        driver.find_element_by_link_text('Student Information').click()
        if len(driver.find_elements_by_class_name('datadisplaytable')) >= 1:

            for table in driver.find_elements_by_class_name('datadisplaytable'):
                stuff = table.find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')
                for i in range(len(stuff)):
                    if stuff[i].text == "Current Program":
                        degree = stuff[i+1].text

                    if stuff[i].text[0:7] == "Major: ":
                        majors = addMajor(majors,degree,stuff[i].text[7:])
                    if stuff[i].text[0:22] == "Major and Department: ":
                        majors = addMajor(majors,degree,stuff[i].text[22:])
                    if stuff[i].text[0:21] == "Major Concentration: ":
                        majors = addConcentrationToLastMajor(majors,stuff[i].text[21:])

        driver.back()

        student_record['degrees'] = []
        for m in majors:
            #print ("MAJOR"+m)
            student_record['degrees'].append(m)

        class_list.append(student_record)
        driver.back()


##################################################################
# Gets the info regarding each course of student images with their rcs id
def wasteTimeClicking(driver,seconds):
    counter = 0
    while counter < seconds:
        print("wasting time")

        # click Instructors & Advisors Menu
        driver.find_element_by_link_text('Instructor & Advisor Menu').click()
        time.sleep(5)

        # click Select a Semester or Summer Session
        driver.find_element_by_link_text('Select a Semester or Summer Session').click()
        time.sleep(55)

        counter += 60


##################################################################
# Gets the info regarding each course of student images with their rcs id
def loopOverEWS(driver):

    # read crns from (optional) file
    crns = []
    if len(str(args.ews_file))>0 and os.path.isfile(str(args.ews_file)):
        with open(str(args.ews_file),'r') as f:
            while True:
                my_line = f.readline().strip()
                vals = my_line.split(',')

                section = vals[0]
                crn = vals[1]
                userid = vals[2]
                id = vals[3]
                choice = vals[4]
                message = vals[5]
                
                if len(crn) != 5:
                    break

                print ("LOOP OVER EWS");
                print (f"CRN {crn} ID {id} CHOICE {choice} MESSAGE {message}")

                # Get the term to use to save images
                term, success = selectTerm(driver)
                if success:
                    print(f"TERM {term}")
          
                    # click Summary Class List & Electronic Warning System (EWS)
                    SelectACRN(driver,crn)
                    SelectAStudent(driver,id)

                    #print("a")
                    #input()
                    
                    warning_code = Select(driver.find_element_by_name('warn_code'))
                                              
                    #print("b")
                    #input()                   
                    if choice=="FAILING":
                        warning_code.select_by_visible_text("Failing the Course")
                    elif choice=="MISSING_INCOMPLETE_HW":
                        warning_code.select_by_visible_text("Missing/Poor Assignments")
                    elif choice=="TEST_PERFORMANCE":
                        warning_code.select_by_visible_text("Test Performance")
                    else:
                        print ("WHOOPS" + choice)
                        exit()
                        
                    warning_comments = driver.find_element_by_name('comments')
                    #print("c")
                    #input()

                    warning_comments.clear()
                    warning_comments.send_keys(message)
                    warning_comments.send_keys(Keys.TAB)
                    warning_comments.send_keys(Keys.RETURN)

                    #print("d")
                    #input()
                                               
                    #driver.find_element_by_link_text('Summary Class List & Electronic Warning System (EWS)').click()

                    print ("press 'y' to submit warning")
                    val = input()                    
                    if val == 'y':
                        driver.find_element_by_xpath("//input[@value='Submit']").click()
                    else:
                        print (f"DOING NOTHING (pressed {val} not 'y')")

                else:
                    print ("FAIL!")
                    exit()

                #crns.append(crn)
    print ("SUCCESS!")
    exit()


def SelectACRN(driver,crn):

    # click Course Information- Select a CRN
    driver.find_element_by_link_text('Course Information- Select a CRN').click()

    driver.find_element_by_link_text('Enter Section Identifier (CRN) Directly').click()
    print ("SELECT CRN  "+crn)
    crn_box = driver.find_element_by_name('CRN')
    crn_box.clear()
    crn_box.send_keys(crn)
    crn_box.send_keys(Keys.TAB)
    crn_box.send_keys(Keys.RETURN)
    #getStudentInfoFromCourse(driver, term)

    print ("Finished processing CRN "+crn)
    return



def SelectAStudent(driver,id):

    driver.find_element_by_link_text('Summary Class List & Electronic Warning System (EWS)').click()
        
    print (f"SELECT STUDENT {id}")

    student_list = driver.find_elements_by_class_name('datadisplaytable')[2].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')
    #print (len(student_list))

    # find which column is the "Student Name" column, since it isn't always the same column number
    student_headers = student_list[0].find_elements_by_tag_name('th')
    stu_col = -1
    id_col = -1
    ews_col = -1
    for i in range(len(student_headers)):
        if student_headers[i].text == "Student Name":
            stu_col = i
        if student_headers[i].text == "ID":
            id_col = i
        if student_headers[i].text == "Electronic\nWarning\nSystem" or student_headers[i].text == "Electronic":
            ews_col = i
        #print (f"{i} {student_headers[i].text}")
            
    if stu_col < 0:
        print("Error: Could not find a column labeled \"Student Name\"!")
        return 0
    if id_col < 0:
        print("Error: Could not find a column labeled \"ID\"!")
        return 0
    if ews_col < 0:
        print("Error: Could not find a column labeled \"Electronic Warning System\"!")
        return 0
    
    for s in range(1, len(student_list)):
        student_record = {}
        student = driver.find_elements_by_class_name('datadisplaytable')[2].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')[s]

        # NOTE: uncomment these line to help with debugging
        #print('Row Number: ' + str(s))
        #print('Row Length: ' + str(len(student.find_elements_by_tag_name('td'))))
        #print('Cell Value: ' + student.find_elements_by_tag_name('td')[stu_col].text)
        
        full_name_cell = student.find_elements_by_tag_name('td')[stu_col].text
        full_name_cell_split = full_name_cell.split(', ')
 
        id_data = student.find_elements_by_tag_name('td')[id_col].text

        if id_data == id:
            print (f"{s}  full_name_cell {full_name_cell} ID '{id_data}'")
            print ("FOUND IT")

            try:
                student.find_elements_by_tag_name('td')[ews_col].find_element_by_class_name('fieldmediumtext').click()
                print ("SUCCESS")
            
            except:
                print ("FAILURE")
            
            #input()
            return
            
                
    print ("COULDN'T FIND STUDENT")
    input()
    return



'''
    

    # otherwise, query the user for which crns to scrape
    else:
        # check if there are any sections assigned for this term
        if len(driver.find_elements_by_class_name('warningtext')) == 1:
            print ("Error: No sections assigned for this term!")
            return

        # iterate and ask if user wants images/names from this course
        select_course = Select(driver.find_element_by_name('crn'))
        options_course = select_course.options

        for index in range(len(options_course)):
            select_course = Select(driver.find_element_by_name('crn'))
            options_course = select_course.options
            course = options_course[index].text

            # gets the images the user wants for the class section by looping until the user enters a valid command
            while True:
                # asks if user wants pictures from current course displayed
                print("Do you want pictures from {}?".format(course))
                answer = input("Y/N/Exit\n").lower()
                if answer == "n":
                    break
                elif answer == "exit":
                    return
                elif answer == "y":
                    print ("Getting student pictures...  (this could take a few seconds per student)")
                    select_course.select_by_index(index)
                    driver.find_element_by_xpath("//input[@value='Submit']").click()
                    getStudentInfoFromCourse(driver, term)
                    break
                else:
                    print("Invalid answer! Try again!")
'''

##################################################################
if __name__ == "__main__":
    try:
        driver, success = login()

        # if login is valid with correct User ID or PIN, continue the program by collecting data
        if success:
            loopOverEWS(driver)

            if success:
                sttime = datetime.now().strftime('%Y%m%d %H:%M:%S')
                with open("last_completed_run.txt", 'a') as logfile:
                    logfile.write(sttime + ' completed scrape\n')


    finally:
        # ends the program
        try:
            driver.quit()
        except:
            pass #If we got an exception in login(), driver will not exist in this scope

import sys
import json
import time
import imghdr
import argparse
import getpass
import requests
import os
from pathlib import Path
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from datetime import datetime

##################################################################
# a few optional command line argument variables
parser = argparse.ArgumentParser(description="RPI SIS Photo and Registration Scraper")
parser.add_argument(
    "--credentials_file",
    type=str,
    default="",
    help="a file containing the user RIN and PIN",
)
parser.add_argument(
    "--term_file", type=str, default="", help="a file containing the term"
)
parser.add_argument(
    "--crn_file",
    type=str,
    default="",
    help="a file containing the crns of desired courses",
)
parser.add_argument(
    "--headless",
    default=False,
    action="store_true",
    help="run program without visual display",
)
parser.add_argument(
    "--no_photos", default=False, action="store_true", help="dont save photos"
)
parser.add_argument(
    "--run_forever",
    default=False,
    action="store_true",
    help="keep clicking to avoid auto-timeout",
)
parser.add_argument(
    "--crns_only",
    default=False,
    action="store_true",
    help="Fetch CRNs for CSCI courses in upcoming term (used for testing)",
)

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

    # By default we launch the display and allow visual debugging
    if args.headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")

    # read credentials from (optional) file
    if len(args.credentials_file) > 0 and os.path.isfile(args.credentials_file):
        with open(str(args.credentials_file), "r") as f:
            rcsid = f.readline().strip()
            passwd = f.readline().strip()
    else:
        rcsid = input("RCS ID: ")
        passwd = getpass.getpass("Password: ")

    print("Setting up selenium", file=sys.stderr)
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)

    # open SIS
    driver.get("https://sis.rpi.edu")

    try:
        print("Logging in", file=sys.stderr)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        driver.find_element(By.ID, "username").send_keys(rcsid)
        driver.find_element(By.ID, "password").send_keys(passwd)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()

        if len(driver.find_elements(By.CSS_SELECTOR, "p.output--error")) > 0:
            print("Incorrect password", file=sys.stderr)
            return driver, False

        print("2FA: enter code on your phone", file=sys.stderr)
        driver.implicitly_wait(25)
        driver.find_element(By.ID, "dont-trust-browser-button").click()
        driver.implicitly_wait(10)
        driver.find_element(
            By.CSS_SELECTOR, 'a[href="/rss/twbkwbis.P_GenMenu?name=bmenu.P_MainMnu"]'
        )

        return driver, True
    except NoSuchElementException:
        print("Failed to login", file=sys.stderr)
        return driver, False


##################################################################
# Gets the session/term the user wants
def selectTerm(driver):
    # read term from (optional) file
    term = ""
    if len(str(args.term_file)) > 0 and os.path.isfile(str(args.term_file)):
        with open(str(args.term_file), "r") as f:
            term = f.readline().strip()

    # click Instructors & Advisors Menu
    driver.find_element(By.LINK_TEXT, "Instructor & Advisor Menu").click()

    # click Select a Semester or Summer Session
    driver.find_element(By.LINK_TEXT, "Select a Semester or Summer Session").click()

    # grab the list of available terms
    select_term = Select(driver.find_element(By.NAME, "term"))
    options_term = select_term.options

    # loop (querying live user) until we have a valid term
    foundTerm = False
    while not foundTerm:
        # print the available sessions/terms
        if term == "":
            print("Here are the available Sessions/Terms:")
            for index in range(len(options_term)):
                print("[{0}] {1}".format(index, options_term[index].text))
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
    driver.find_element(By.XPATH, "//input[@value='Submit']").click()

    return term, True


##################################################################
# Saves the images with rcs id as image name to a term/course folder
def saveImagesToFolder(term, class_list):
    if len(class_list) == 0:
        return

    course_crn = class_list[0]["course_crn"]
    course_prefix = class_list[0]["course_prefix"]
    course_name = class_list[0]["course_name"]
    course_section = class_list[0]["course_section"]
    course_number = class_list[0]["course_number"]

    course_folder_name = "{}-{}-{}".format(course_prefix, course_number, course_section)

    # make term (month year) into month-year
    term_elements = term.split()
    folder_term = term_elements[0] + "-" + term_elements[1]

    # get path and create path if not already existed
    path = Path(folder_term, course_folder_name)
    path.mkdir(exist_ok=True, parents=True)

    jsonfile = []

    # loops through the class list of dictionaries of student info
    for i in range(len(class_list)):
        obj = {}
        obj["full_name"] = class_list[i]["name"]
        obj["first_name"] = class_list[i]["first_name"]
        obj["middle_name"] = class_list[i]["middle_name"]
        obj["last_name"] = class_list[i]["last_name"]
        obj["degrees"] = class_list[i]["degrees"]

        obj["rin"] = class_list[i]["rin"]
        if "rcs" not in class_list[i]:
            obj["rcs"] = ""
            print(f"Warning: no RCS for {class_list[i]['name']}")
        else:
            obj["rcs"] = class_list[i]["rcs"]
        if "email" not in class_list[i]:
            obj["email"] = ""
            print(f"Warning: no email for {class_list[i]['name']}")
        else:
            obj["email"] = class_list[i]["email"]

        obj["course_crn"] = class_list[i]["course_crn"]
        obj["course_prefix"] = class_list[i]["course_prefix"]
        obj["course_name"] = class_list[i]["course_name"]
        obj["course_section"] = class_list[i]["course_section"]
        obj["course_number"] = class_list[i]["course_number"]
        obj["term"] = class_list[i]["term"]

        jsonfile.append(obj)
        for k in class_list[i].keys():
            # no email available on SIS for this student so label the image with error_first_last.png
            if len(class_list[i]) == 2:
                if k == "name":
                    name_str = class_list[i].get(k).split()
                    first_name = name_str[0]
                    last_name = name_str[1]
                    rcs_id = "error-{}-{}".format(first_name, last_name)
                    print("NAMESTR=" + name_str)
                    print("first_name=" + first_name)
                    print("last_name=" + last_name)
                    print("rcs_id" + rcs_id)
            # if there is an email address, assign letters before "@rpi.edu" to rcs_id
            if k == "email":
                rcs_id = class_list[i].get(k)[:-8]
            # regardless if email or not, get image if the current dict key is img url
            if k == "img url":
                img_url = class_list[i].get(k)
        # download and save the image to a specific folder (term/course_section) from the image url
        if args.no_photos:
            continue
        if img_url.split("/")[-1].strip() == "web_transparent.gif":
            print("Skipping {} because no photo on SIS".format(rcs_id))
            continue
        r = requests.get(img_url)

        # Deduce the extension, build the output path
        img_format = imghdr.what(None, r.content).lower()
        img_name = rcs_id + "." + img_format
        filepath = path / img_name

        # Actually write the file. We could skip the context manager and just use Image.save(filepath)
        with open(str(filepath), "wb") as f:
            f.write(r.content)
            print("Saved photo for student rcs {}".format(rcs_id))

    term_string = term.replace(" ", "_")
    filename = "all_json/" + term_string + "_" + course_crn + ".json"

    with open(filename, "w") as f:
        json.dump(jsonfile, f, indent=4, sort_keys=True)


##################################################################
# returns the class list of dictionaries of info collected about each student's img url, name, and email
def getStudentInfoFromCourse(driver, term):

    class_list = []

    # click Summary Class List & Electronic Warning System (EWS)
    driver.find_element(
        By.LINK_TEXT, "Summary Class List & Electronic Warning System (EWS)"
    ).click()

    try:
        current_record = driver.find_element(By.PARTIAL_LINK_TEXT, "Current Record Set")
        # print ("'Current Record Set' label found")
        try:
            first = driver.find_element(
                By.PARTIAL_LINK_TEXT, "Current Record Set: 1 - 200"
            )
            print("1-200 found")
            getStudentInfoFromCourseHelper(driver, term, class_list)
            print("1-200 finished")
            try:
                second = driver.find_element(By.PARTIAL_LINK_TEXT, "201 -")
                print("201-?? found")
                second.click()
                getStudentInfoFromCourseHelper(driver, term, class_list)
                driver.back()
                print("201-?? finished")
            except:
                print("ERROR IN CURRENT RECORD COUNTING -- SECOND")
                return 0
        except:
            print("ERROR IN CURRENT RECORD COUNTING -- FIRST")
            return 0
    except:
        # print ("'Current Record Set' label not found")
        getStudentInfoFromCourseHelper(driver, term, class_list)

    driver.back()
    driver.back()

    if class_list == 0:
        print("Warning: this class size is 0")
    else:
        # Use the info collected and save the image with rcs id for term/course in current directory
        saveImagesToFolder(term, class_list)


##################################################################
def addMajor(majors, degree, text):
    majors.append(degree + " / " + text)
    return majors


def addConcentrationToLastMajor(majors, text):
    majors[-1] = majors[-1] + " / " + text
    return majors


##################################################################
# returns the class list of dictionaries of info collected about each student's img url, name, and email
def getStudentInfoFromCourseHelper(driver, term, class_list):

    # check if class is size 0
    if len(driver.find_elements(By.CLASS_NAME, "errortext")) == 1:
        print("Error: Class size is 0!")
        return 0

    COURSENAMESTRING = (
        driver.find_elements(By.CLASS_NAME, "datadisplaytable")[0]
        .find_element(By.TAG_NAME, "tbody")
        .find_elements(By.TAG_NAME, "tr")[0]
        .find_elements(By.TAG_NAME, "th")[0]
        .text
    )

    COURSENAMESTRING_split = COURSENAMESTRING.split(" - ")
    if len(COURSENAMESTRING_split) < 2:
        print("ERROR: course name formatting bug")
        return 0
    COURSENAME = ""
    for index in range(len(COURSENAMESTRING_split) - 1):
        if index > 0:
            COURSENAME = COURSENAME + " - "
        COURSENAME = COURSENAME + COURSENAMESTRING_split[index]

    print("COURSE NAME IS " + COURSENAME)

    if len(COURSENAMESTRING_split[-1]) != 12:
        print("ERROR: course prefix / code bug")
        return 0
    COURSEPREFIX = COURSENAMESTRING_split[-1][0:4]
    COURSENUMBER = COURSENAMESTRING_split[-1][5:9]
    COURSESECTION = COURSENAMESTRING_split[-1][10:]

    CRNSTRING = (
        driver.find_elements(By.CLASS_NAME, "datadisplaytable")[0]
        .find_element(By.TAG_NAME, "tbody")
        .find_elements(By.TAG_NAME, "tr")
    )
    CRNSTRING = str(CRNSTRING[1].text)
    if CRNSTRING[0:5] == "CRN: ":
        CRNSTRING = CRNSTRING[5:]
    else:
        print("ERROR: could not find CRN")
        return 0

    # find link for pic
    student_list = (
        driver.find_elements(By.CLASS_NAME, "datadisplaytable")[2]
        .find_element(By.TAG_NAME, "tbody")
        .find_elements(By.TAG_NAME, "tr")
    )

    # find which column is the "Student Name" column, since it isn't always the same column number
    student_headers = student_list[0].find_elements(By.TAG_NAME, "th")
    stu_col = -1
    id_col = -1
    for i in range(len(student_headers)):
        if student_headers[i].text == "Student Name":
            stu_col = i
        if student_headers[i].text == "ID":
            id_col = i

    if stu_col < 0:
        print('Error: Could not find a column labeled "Student Name"!')
        return 0

    if id_col < 0:
        print('Error: Could not find a column labeled "ID"!')
        return 0

    # NOTE: uncomment this line to help with debugging
    # print("Student column: " + str(stu_col))

    # loop through list of students to get image, name, and email
    # all info collected from for loop (img url, name, email) put into dict
    for s in range(1, len(student_list)):
        student_record = {}
        student = (
            driver.find_elements(By.CLASS_NAME, "datadisplaytable")[2]
            .find_element(By.TAG_NAME, "tbody")
            .find_elements(By.TAG_NAME, "tr")[s]
        )

        # NOTE: uncomment these line to help with debugging
        # print('Row Number: ' + str(s))
        # print('Row Length: ' + str(len(student.find_elements(By.TAG_NAME, 'td'))))
        # print('Cell Value: ' + student.find_elements(By.TAG_NAME, 'td')[stu_col].text)

        full_name_cell = student.find_elements(By.TAG_NAME, "td")[stu_col].text
        full_name_cell_split = full_name_cell.split(", ")
        # format of the full name appears to be one of:
        #    Smith, John X.             (with middle initial)
        #    Smith, John                (with no middle name/initial)
        #    Smith Jones, John Edward   (spaces in first & last name are ok)
        if len(full_name_cell_split) == 2:
            last_name = full_name_cell_split[0]
            first_name = full_name_cell_split[1]
            middle_name = ""
            first_name_length = len(first_name)
            if (
                first_name_length > 3
                and first_name[first_name_length - 3] == " "
                and first_name[first_name_length - 1] == "."
            ):
                middle_name = first_name[first_name_length - 2 :]
                first_name = first_name[0 : first_name_length - 3]

        id_rin = student.find_elements(By.TAG_NAME, "td")[id_col].text

        try:
            student.find_elements(By.TAG_NAME, "td")[stu_col].find_element(
                By.CLASS_NAME, "fieldmediumtext"
            ).click()
        except:
            input()
            raise

        img_url = driver.current_url
        driver.get(img_url)

        # image, initalize to empty string
        student_record["img url"] = ""
        image_arr = driver.find_elements(By.TAG_NAME, "img")

        # do search through all <img> tags for first non-header-layout tag
        # have to skip 2 more <img> tags because they are transparent images
        for i in range(len(image_arr)):
            if image_arr[i].get_attribute("NAME") != "web_tab_corner_right":
                student_record["img url"] = image_arr[i + 2].get_attribute("src")
                # Uncomment this line to print the image URLs we are attempting, useful for debugging
                # print("found non-match, +2 is " + student_record['img url'])
                break

        # name
        info_name = (
            driver.find_elements(By.CLASS_NAME, "plaintable")[4]
            .find_element(By.TAG_NAME, "tbody")
            .find_element(By.TAG_NAME, "tr")
            .find_elements(By.TAG_NAME, "td")[1]
            .text
        )

        name = info_name[16:]
        student_record["name"] = name
        student_record["rin"] = id_rin

        student_record["first_name"] = first_name
        student_record["middle_name"] = middle_name
        student_record["last_name"] = last_name

        student_record["course_name"] = COURSENAME
        student_record["course_number"] = COURSENUMBER
        student_record["course_prefix"] = COURSEPREFIX
        student_record["course_crn"] = CRNSTRING
        student_record["course_section"] = COURSESECTION

        student_record["term"] = term

        print("Gathering info for student: " + name)

        # email address
        driver.find_element(By.LINK_TEXT, "Student E-mail Address").click()
        if len(driver.find_elements(By.CLASS_NAME, "datadisplaytable")) == 1:
            emails = (
                driver.find_element(By.CLASS_NAME, "datadisplaytable")
                .find_element(By.TAG_NAME, "tbody")
                .find_elements(By.TAG_NAME, "tr")
            )
            for i in range(len(emails)):
                if emails[i].text == "Campus Student Email Address":
                    email = emails[i + 1].find_element(By.TAG_NAME, "td").text
                    student_record["email"] = email
                    student_record["rcs"] = email[0 : len(email) - 8]
                    break
        driver.back()

        degree = "UNKNOWN"
        majors = []

        # undergraduate major
        driver.find_element(By.LINK_TEXT, "Student Information").click()
        if len(driver.find_elements(By.CLASS_NAME, "datadisplaytable")) >= 1:

            for table in driver.find_elements(By.CLASS_NAME, "datadisplaytable"):
                stuff = table.find_element(By.TAG_NAME, "tbody").find_elements(
                    By.TAG_NAME, "tr"
                )
                for i in range(len(stuff)):
                    if stuff[i].text == "Current Program":
                        degree = stuff[i + 1].text

                    if stuff[i].text[0:7] == "Major: ":
                        majors = addMajor(majors, degree, stuff[i].text[7:])
                    if stuff[i].text[0:22] == "Major and Department: ":
                        majors = addMajor(majors, degree, stuff[i].text[22:])
                    if stuff[i].text[0:21] == "Major Concentration: ":
                        majors = addConcentrationToLastMajor(majors, stuff[i].text[21:])

        driver.back()

        student_record["degrees"] = []
        for m in majors:
            # print ("MAJOR"+m)
            student_record["degrees"].append(m)

        class_list.append(student_record)
        driver.back()


##################################################################
# Gets the info regarding each course of student images with their rcs id
def wasteTimeClicking(driver, seconds):
    counter = 0
    while counter < seconds:
        print("wasting time")

        # click Instructors & Advisors Menu
        driver.find_element(By.LINK_TEXT, "Instructor & Advisor Menu").click()
        time.sleep(5)

        # click Select a Semester or Summer Session
        driver.find_element(By.LINK_TEXT, "Select a Semester or Summer Session").click()
        time.sleep(55)

        counter += 60


##################################################################
# Gets the info regarding each course of student images with their rcs id
def loopOverCourses(driver, term):
    # read crns from (optional) file
    crns = []
    if len(str(args.crn_file)) > 0 and os.path.isfile(str(args.crn_file)):
        with open(str(args.crn_file), "r") as f:
            while True:
                crn = f.readline().strip()
                if len(crn) != 5:
                    break
                crns.append(crn)

    # make a directory to hold the registration directories
    os.makedirs("all_json", exist_ok=True)

    # click Course Information- Select a CRN
    driver.find_element(By.LINK_TEXT, "Course Information- Select a CRN").click()

    # if there was at least one crn in the file
    if crns:
        driver.find_element(
            By.LINK_TEXT, "Enter Section Identifier (CRN) Directly"
        ).click()
        for crn in crns:
            print("Begin processing CRN " + crn)
            crn_box = driver.find_element(By.NAME, "CRN")
            crn_box.clear()
            crn_box.send_keys(crn)
            crn_box.send_keys(Keys.TAB)
            crn_box.send_keys(Keys.RETURN)
            getStudentInfoFromCourse(driver, term)
            print("Finished processing CRN " + crn)
        return

    # otherwise, query the user for which crns to scrape
    else:
        # check if there are any sections assigned for this term
        if len(driver.find_elements(By.CLASS_NAME, "warningtext")) == 1:
            print("Error: No sections assigned for this term!")
            return

        # iterate and ask if user wants images/names from this course
        select_course = Select(driver.find_element(By.NAME, "crn"))
        options_course = select_course.options

        for index in range(len(options_course)):
            select_course = Select(driver.find_element(By.NAME, "crn"))
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
                    print(
                        "Getting student pictures...  (this could take a few seconds per student)"
                    )
                    select_course.select_by_index(index)
                    driver.find_element(By.XPATH, "//input[@value='Submit']").click()
                    getStudentInfoFromCourse(driver, term)
                    break
                else:
                    print("Invalid answer! Try again!")


# Assumes SIS main page is open
def get_csci_crns(driver):
    print("Fetching CSCI CRNs")
    driver.find_element(By.LINK_TEXT, "SITE MAP").click()
    driver.find_element(By.LINK_TEXT, "Class Search").click()

    driver.find_element(
        By.XPATH, "/html/body/div[3]/form/table/tbody/tr/td/select/option[2]"
    ).click()
    driver.find_element(By.CSS_SELECTOR, 'input[type="submit"][value="Submit"]').click()
    driver.find_element(By.CSS_SELECTOR, 'option[value="CSCI"]').click()
    driver.find_element(
        By.CSS_SELECTOR, 'input[type="submit"][value="Section Search"]'
    ).click()
    return [
        crn_link.text
        for crn_link in driver.find_elements(
            By.CSS_SELECTOR, 'a[href^="/rss/bwckschd.p_disp_listcrse"]'
        )
    ]


##################################################################
if __name__ == "__main__":
    driver, success = login()

    # if login is valid with correct User ID or PIN, continue the program by collecting data
    if not success:
        driver.quit()
    else:
        if args.crns_only:
            crns = get_csci_crns(driver)
            print(crns)
            sys.exit(0)

        while True:
            # Get the term to use to save images
            term, success = selectTerm(driver)

            if success:
                loopOverCourses(driver, term)

                sttime = datetime.now().strftime("%Y%m%d %H:%M:%S")
                with open("last_completed_run.txt", "a") as logfile:
                    logfile.write(sttime + " completed scrape\n")

            if not args.run_forever:
                print(
                    "--------------------\nlets NOT run forever\n--------------------"
                )
                break

            # wait a number of hours before doing it all again
            num_hours = 1
            wasteTimeClicking(driver, 60 * 60 * num_hours)
            print("----------------\nLETS RUN FOREVER\n----------------")

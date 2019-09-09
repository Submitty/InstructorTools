import imghdr
import getpass, requests, os, re
from pathlib import Path
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
chrome_options = Options()
chrome_options.add_argument("--headless")
from selenium.webdriver.common.keys import Keys

#Workaround for if pyopenssl is installed and we want weak keys
try:
    from urllib3.contrib import pyopenssl
    pyopenssl.extract_from_urllib3()
except ImportError:
    pass

# Login to SIS
def login(driver):
    # Get RIN and PIN
    rin_id = input("RIN: ")
    pin_id = getpass.getpass("PIN: ")

    # Click into login page
    try:
        driver.find_element_by_link_text('Login').click()
    except NoSuchElementException:
        pass

    # Types in RIN and PIN in login page
    rin = driver.find_element_by_name('sid')
    rin.send_keys(rin_id)
    pin = driver.find_element_by_name('PIN')
    pin.send_keys(pin_id)

    # click login button
    driver.find_element_by_xpath("//input[@value='Login']").click()
    # checks to see if login credentials work- if not, return False and end program
    if "Authorization Failure - Invalid User ID or PIN." in driver.page_source:
        print("Authorization Failure - Invalid User ID or PIN.")
        return False
    return True


# Gets the session/term the user wants
def getSession(driver):
    # click Instructors & Advisors Menu
    driver.find_element_by_link_text('Instructor & Advisor Menu').click()

    # click Select a Semester or Summer Session
    driver.find_element_by_link_text('Select a Semester or Summer Session').click()

    # iterate and ask for a term
    select_term = Select(driver.find_element_by_name('term'))
    options_term = select_term.options

    print("Here are the following Semester/Summer Sessions:")
    # print the available sessions/terms
    for option in options_term:
        print(option.text)

    # gets the term the user wants by looping until the user enters Exit or a valid term
    foundTerm = False
    while not foundTerm:
        term = input("Select a term ( or Exit to terminate ): ")
        # if user does not wish to continue, exit
        if term == "Exit":
            return term
        # loops through all the term options to see if there is a match
        for index in range(len(options_term)):
            if options_term[index].text == term:
                select_term.select_by_index(index)
                foundTerm = True
                break
        # if no match with any term options, print out that the term cannot be found
        if not foundTerm:
            print("Cannot find the term")

    # click submit button
    driver.find_element_by_xpath("//input[@value='Submit']").click()
    return term


# Saves the images with rcs id as image name to a term/course folder
def saveImagesToFolder(term, course, class_list):
    # create shortened name for class folder
    course_name = re.match(r'([A-Z]{4}) ([0-9]{4}) ([0-9]+)\:',course)
    if course_name is None:
        print ("Invalid format for course name")
        return
    course_folder_name = "{}-{}-{}".format(*course_name.groups())

    # make term (month year) into month-year
    term_elements = term.split()
    folder_term = term_elements[0]+"-"+term_elements[1]

    # get path and create path if not already existed
    path = Path(folder_term, course_folder_name)
    path.mkdir(exist_ok=True, parents=True)

    # loops through the class list of dictionaries of student info
    for i in range(len(class_list)):
        for k in class_list[i].keys():
            # no email available on SIS for this student so label the image with error_first_last.png
            if len(class_list[i]) == 2:
                if k == "name":
                    name_str = class_list[i].get(k).split()
                    first_name = name_str[0]
                    last_name = name_str[1]
                    rcs_id = "error-{}-{}".format(first_name, last_name)
            # if there is an email address, assign letters before "@rpi.edu" to rcs_id
            if k == "email":
                rcs_id = class_list[i].get(k)[:-8]
            # regardless if email or not, get image if the current dict key is img url
            if k == "img url":
                img_url = class_list[i].get(k)
        # download and save the image to a specific folder (term/course_section) from the image url
        if img_url.split("/")[-1].strip() == "web_transparent.gif":
            print("Skipping {} because no photo on SIS".format(rcs_id))
            continue
        r = requests.get(img_url)

        #Deduce the extension, build the output path
        img_format = imghdr.what(None,r.content).lower()
        img_name = rcs_id + "." + img_format
        filepath = path / img_name

        #Actually write the file. We could skip the context manager and just use Image.save(filepath)
        with open(str(filepath),'wb') as f:
            f.write(r.content)
            print("Saved photo for student rcs {}".format(rcs_id))

# returns the class list of dictionaries of info collected about each student's img url, name, and email
def getStudentInfoFromCourse(driver, select_course, index, class_list):
    select_course.select_by_index(index)
    # click submit button
    driver.find_element_by_xpath("//input[@value='Submit']").click()

    # click Summary Class List & Electronic Warning System (EWS)
    driver.find_element_by_link_text('Summary Class List & Electronic Warning System (EWS)').click()

    # check if class is size 0
    if len(driver.find_elements_by_class_name('errortext')) == 1:
        driver.back()
        driver.back()
        print("Error: Class size is 0!")
        return 0

    # find link for pic
    student_list = driver.find_elements_by_class_name('datadisplaytable')[2].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')

    # find which column is the "Student Name" column, since it isn't always the same column number
    student_headers = student_list[0].find_elements_by_tag_name('th')
    stu_col = -1
    for i in range(len(student_headers)):
        if student_headers[i].text == "Student Name":
            stu_col = i
    if stu_col <0:
        driver.back()
        driver.back()
        print("Error: Could not find a column labeled \"Student Name\"!")
        return 0

    print("Student column: " + stu_col)

    # loop through list of students to get image, name, and email
    # all info collected from for loop (img url, name, email) put into dict
    for s in range(1, len(student_list)):
        student_record = {}
        student = driver.find_elements_by_class_name('datadisplaytable')[2].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')[s]
        print('Row Number: ' + str(s))
        print('Row Length: ' + str(len(student.find_elements_by_tag_name('td'))))
        print('Cell Value: ' + student.find_elements_by_tag_name('td')[stu_col].text)
        student.find_elements_by_tag_name('td')[stu_col].find_element_by_class_name('fieldmediumtext').click()

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

        print("Gathering info for student: "+name)

        # email address
        driver.find_element_by_link_text('Student E-mail Address').click()
        if len(driver.find_elements_by_class_name('datadisplaytable')) == 1:
            emails = driver.find_element_by_class_name('datadisplaytable').find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')
            for i in range(len(emails)):
                if emails[i].text == "Campus Student Email Address":
                    email = emails[i+1].find_element_by_tag_name('td').text
                    student_record['email'] = email
                    break
        class_list.append(student_record)
        driver.back()
        driver.back()
    driver.back()
    driver.back()
    return class_list


# Gets the info regarding each course of student images with their rcs id
def getInfoFromCourse(driver):
    # Get the term to use to save images
    term = getSession(driver)
    if term == "Exit":
        return

    # click Course Information- Select a CRN
    driver.find_element_by_link_text('Course Information- Select a CRN').click()

    # check if there are any sections assigned for this term
    if len(driver.find_elements_by_class_name('warningtext')) == 1:
        print ("Error: No sections assigned for this term!")
        return

    # iterate and ask if user wants images/names from this course
    select_course = Select(driver.find_element_by_name('crn'))
    options_course = select_course.options

    for index in range(len(options_course)):
        # all dicts put into list for each class section
        class_list = []
        select_course = Select(driver.find_element_by_name('crn'))
        options_course = select_course.options
        course = options_course[index].text

        # gets the images the user wants for the class section by looping until the user enters a valid command
        foundAnswer = False
        while not foundAnswer:
            # asks if user wants pictures from current course displayed
            print("Do you want pictures from {}?".format(course))
            answer = input("Y/N/Exit\n").lower()
            if answer == "n":
                break
            elif answer == "exit":
                return
            elif answer == "y":
                print ("Getting student pictures...  (this could take a few seconds per student)")
                # get the class list of dictionary of email, name, and image per student
                class_list = getStudentInfoFromCourse(driver, select_course, index, class_list)
                if class_list == 0:
                    break
                # Use the info collected and save the image with rcs id for term/course in current directory
                saveImagesToFolder(term, course, class_list)
                foundAnswer = True
            else:
                print("Invalid answer! Try again!")

if __name__ == "__main__":
    #Just setting the default ciphers (for this session) to be weak DES/SHA for SIS compatibility
    #Be careful about navigating to any other sites...

    requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'DES-CBC3-SHA:AES128-SHA:'+requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS
    driver = webdriver.Chrome(options=chrome_options)
    try:
        # open SIS
        driver.get('https://sis.rpi.edu/')
        # if login is valid with correct User ID or PIN, continue the program by collecting data
        if login(driver):
            getInfoFromCourse(driver)
    finally:
        # ends the program
        driver.quit()

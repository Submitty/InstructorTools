import getpass
import urllib
import os
from selenium.webdriver.support.ui import Select
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

# Login to SIS
def login(driver):
    # Get User ID and PIN 
    user_id = getpass.getpass("User ID: ")
    pin_id = getpass.getpass("PIN: ")

    # Click into login page
    driver.find_element_by_link_text('Login').click()

    # Types in username and pin in login page
    username = driver.find_element_by_name('sid')
    username.send_keys(user_id)
    pin = driver.find_element_by_name('PIN')
    pin.send_keys(pin_id)

    # click login button
    driver.find_element_by_xpath("//input[@value='Login']").click()
    # checks to see if login credentials work- if not, return False and end program
    if "Authorization Failure - Invalid User ID or PIN." in driver.page_source:
        print("Authorization Failure - Invalid User ID or PIN.")
        return False


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
    # get path and create path if not already existed
    path = "{}/{}".format(term, course)
    os.makedirs(path, exist_ok=True)
    
    # loops through the class list of dictionaries of student info
    for class in class_list:
        for k in class_list[i].keys():
            # no email available on SIS for this student so label the image with error_first_last.png
            if len(class) == 2:
                if k == "name":
                    name_str = class.get(k).split(None, 3)
                    first_name = name_str[0]
                    last_name = name_str[1]
                    rcs_id = "error_{}_{}".format(first_name, last_name)
            # if there is an email address, assign letters before "@rpi.edu" to rcs_id
            if k == "email":
                rcs_id = class.get(k)[:-8]
            # Regardless if email or not, get image if the current dict key is img url
            if k == "img url":
                img_url = class.get(k)
        urllib.request.urlretrieve(img_url, path + "/" + rcs_id + ".png") 


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
    
    # loop through list of students to get image, name, and email
    # all info collected from for loop (img url, name, email) put into dict
    for s in range(1, len(student_list)):
        student_record = {}             
        student = driver.find_elements_by_class_name('datadisplaytable')[2].find_element_by_tag_name('tbody').find_elements_by_tag_name('tr')[s]          
        student.find_elements_by_tag_name('td')[1].find_element_by_class_name('fieldmediumtext').click()
        
        img_url = driver.current_url
        driver.get(img_url)   
        
        # image
        image = driver.find_elements_by_tag_name('img')[6].get_attribute('src')
        student_record['img url'] = image
        
        # name
        info_name = driver.find_elements_by_class_name('plaintable')[4].find_element_by_tag_name('tbody').find_element_by_tag_name('tr').find_elements_by_tag_name('td')[1].text
        name = info_name[16:]
        student_record['name'] = name
        
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
            # Asks if user wants pictures from current course displayed
            print("Do you want pictures from {}?".format(course))
            answer = input("Y/N/Exit\n")
            if answer == "N":
                break
            elif answer == "Exit":
                return
            elif answer == "Y":
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
    # Open SIS
    driver = webdriver.Chrome()
    driver.get("https://sis.rpi.edu/")
    
    # if login is invalid with incorrect User ID or PIN, end the program
    if not login(driver):
        driver.close()

    # if login is valid with correct User ID and PIN, continue the program by collecting data
    else:
        getInfoFromCourse(driver)
        driver.close()

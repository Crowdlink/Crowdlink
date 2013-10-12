from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys

import unittest
import os
import sys
import logging
selenium_logger = logging.getLogger('selenium.webdriver.remote.remote_connection')
# Only display possible problems
selenium_logger.setLevel(logging.DEBUG)
root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
root.addHandler(ch)
selenium_logger.addHandler(ch)


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox() # Get local session of firefox
        self.base_url = os.getenv('TESTING_URL', 'http://localhost:8000')

    def test_00_response(self):
        self.driver.get(self.base_url + "/") # Load page
        # simple color check ensures our css is compiled properly
        assert self.driver.execute_script("return $('div.container.header-col.header-col-purple').css('background-color');") == "rgb(93, 73, 111)"
        assert "Featurelet" in self.driver.title

    def test_01_register(self):
        driver = self.driver
        driver.get(self.base_url + "/signup")
        driver.find_element_by_link_text("Sign Up").click()
        driver.find_element_by_id("RegisterForm_username").clear()
        driver.find_element_by_id("RegisterForm_username").send_keys("test")
        driver.find_element_by_id("RegisterForm_password").clear()
        driver.find_element_by_id("RegisterForm_password").send_keys("testing")
        driver.find_element_by_id("RegisterForm_password_confirm").clear()
        driver.find_element_by_id("RegisterForm_password_confirm").send_keys("testing")
        driver.find_element_by_id("RegisterForm_email").clear()
        driver.find_element_by_id("RegisterForm_email").send_keys("isaac@simpload.com")
        driver.find_element_by_id("RegisterForm_submit").click()

    def test_02_logout(self):
        self.test_04_login()
        driver = self.driver
        driver.get(self.base_url + "/")
        driver.find_element_by_link_text("Logout").click()
        try: self.assertEqual("Login", driver.find_element_by_xpath("//div[@id='wrap']/div/div/ul/li[2]/a/span").text)
        except AssertionError as e: self.verificationErrors.append(str(e))

    def test_03_create_project(self):
        self.test_04_login()
        driver = self.driver
        driver.get(self.base_url + "/")
        driver.find_element_by_link_text("Create a New Project").click()
        driver.find_element_by_id("NewProjectForm_ptitle").clear()
        driver.find_element_by_id("NewProjectForm_ptitle").send_keys("yota")
        driver.find_element_by_id("NewProjectForm_source").clear()
        driver.find_element_by_id("NewProjectForm_source").send_keys("http://google.com")
        driver.find_element_by_id("NewProjectForm_create").click()
        driver.get(self.base_url + "/")
        self.assertEqual("yota", str(driver.find_element_by_css_selector("li.list-group-item").text).strip())

    def test_04_login(self):
        driver = self.driver
        driver.get(self.base_url + "/")
        driver.find_element_by_css_selector("i.icon-signin.icon-large").click()
        driver.find_element_by_id("LoginForm_username").clear()
        driver.find_element_by_id("LoginForm_username").send_keys("test")
        driver.find_element_by_id("LoginForm_password").clear()
        driver.find_element_by_id("LoginForm_password").send_keys("testing")
        driver.find_element_by_id("LoginForm_submit").click()
        self.assertEqual("Your feed", driver.find_element_by_css_selector("h3").text)

    def tearDown(self):
        self.driver.close()

if __name__ == '__main__':
        unittest.main()

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time

# URL_GRAFANA = "http://localhost:3000"

# # Open the browser and navigate to the Grafana URL
# driver = webdriver.Chrome()

# try: 
#   driver.get(URL_GRAFANA)
#   time.sleep(5)
#   username_input = driver.find_element(By.XPATH, '//*[@id=":r0:"]')
#   password_input = driver.find_element(By.XPATH,  '//*[@id=":r1:"]')
#   login_button = driver.find_element(By.XPATH, '//*[@id="pageContent"]/div[3]/div/div/div/div[2]/div/div/form/button')

#   new_password = '//*[@id="new-password"]'
#   confirm_password = '//*[@id="confirm-new-password"]'
#   confirm_password_button = '//*[@id="pageContent"]/div[3]/div/div/div/div[2]/div/form/div[5]/button[1]'
#   username_input.send_keys("admin")
#   password_input.send_keys("admin")
#   time.sleep(2)
#   login_button.click()

#   time.sleep(5)

#   if driver.find_element(By.XPATH, new_password):
#     new_password_input = driver.find_element(By.XPATH, new_password)
#     confirm_password_input = driver.find_element(By.XPATH, confirm_password)
#     new_password_input.send_keys("admin")
#     confirm_password_input.send_keys("admin")
#     time.sleep(2)
#     input("Press Enter to continue...")
#     botton_confirm_password = driver.find_element(By.XPATH, confirm_password_button)
#     botton_confirm_password.click()
#     time.sleep(5)

# finally:
#   driver.quit()

# Login to Grafana

# Create a new dashboard

# Add a new panel to the dashboard
class LazyHelper:

  def __init__(self, dns="192.168.15.101"):
    self.driver = webdriver.Chrome()
    self.dns = dns
    self.declare_urls()


  def declare_urls(self, dns="192.168.15.101"):
    self.minio = f"http://{self.dns}:9001"
    self.url_nessie = f"http://{self.dns}:19120"
    self.url_dremio = f"http://{self.dns}:9047"
    self.url_notebook = f"http://{self.dns}:8888"
    self.url_ctrl_center = f"http://{self.dns}:9021"
    self.url_spark_ui = f"http://{self.dns}:18080"
    self.url_grafana = f"http://{self.dns}:3000"

  def open_new_tab_and_switch(self, idx):
    self.driver.execute_script("window.open('about:blank', '_blank');")
    self.driver.switch_to.window(self.driver.window_handles[idx])
    time.sleep(1.5)
  
  def open_notebook(self):
    self.driver.get(self.url_notebook)
    time.sleep(1)

  def open_control_center(self):
    self.driver.get(self.url_ctrl_center)
    time.sleep(1)

  def open_spark_ui(self):
    self.driver.get(self.url_spark_ui)
    time.sleep(1)

  def open_grafana(self):
    self.driver.get(self.url_grafana)
    time.sleep(1)
    # username_input = driver.find_element(By.XPATH, '//*[@id=":r0:"]')
    # password_input = driver.find_element(By.XPATH,  '//*[@id=":r1:"]')
    # login_button = driver.find_element(By.XPATH, '//*[@id="pageContent"]/div[3]/div/div/div/div[2]/div/div/form/button')
    # new_password = '//*[@id="new-password"]'
    # confirm_password = '//*[@id="confirm-new-password"]'
    # confirm_password_button = '//*[@id="pageContent"]/div[3]/div/div/div/div[2]/div/form/div[5]/button[1]'
    # username_input.send_keys("admin")
    # password_input.send_keys("admin")
    # time.sleep(2)
    # login_button.click()
    # time.sleep(5)
    # if driver.find_element(By.XPATH, new_password):
    #   new_password_input = driver.find_element(By.XPATH, new_password)
    #   confirm_password_input = driver.find_element(By.XPATH, confirm_password)
    #   new_password_input.send_keys("admin")
    #   confirm_password_input.send_keys("admin")
    #   time.sleep(2)
    #   input("Press Enter to continue...")
    #   botton_confirm_password = driver.find_element(By.XPATH, confirm_password_button)
    #   botton_confirm_password.click()
    #   time.sleep(5)




if __name__ == '__main__':
  print("OI")
  
  """
  spark_ui =
  """
  open_new_tab = lambda driver: driver.execute_script("window.open('about:blank', '_blank');")
  robot = LazyHelper()

  robot.open_control_center()
  robot.open_new_tab_and_switch(idx=1)
  robot.open_spark_ui()
  robot.open_new_tab_and_switch(idx=2)
  robot.open_notebook()

  try:
      # Example to execute hypothetical CDP command
      robot.driver.execute_cdp_cmd("Page.createTabGroup", {"tabIds": robot.driver.window_handles})
  except Exception as e:
      print("Error creating tab groups: ", e)
  input("Press Enter to continue...")


  # driver.execute_script("window.open('about:blank', '_blank');")
  # driver.switch_to.window(driver.window_handles[1])

  # open_control_center(driver)
  # driver.execute_script("window.open('about:blank', '_blank');")
  # time.sleep(2)
  # driver.switch_to.window(driver.window_handles[2])

  # open_spark_ui(driver)
  # driver.execute_script("window.open('about:blank', '_blank');")
  # driver.switch_to.window(driver.window_handles[3])

  # open_notebook(driver)
  # input("Press Enter to continue...")


  # # Open the browser and navigate to the Grafana URL
  # service = Service(PATH)
  # service.start()
  # driver = webdriver.Remote(service.service_url)
  # driver.get(URL_GRAFANA)

  # try: 
  #   time.sleep(5)
  #   username_input = driver.find_element(By.XPATH, '//*[@id=":r0:"]')
  #   password_input = driver.find_element(By.XPATH,  '//*[@id=":r1:"]')
  #   login_button = driver.find_element(By.XPATH, '//*[@id="pageContent"]/div[3]/div/div/div/div[2]/div/div/form/button')

  #   new_password = '//*[@id="new-password"]'
  #   confirm_password = '//*[@id="confirm-new-password"]'
  #   confirm_password_button = '//*[@id="pageContent"]/div[3]/div/div/div/div[2]/div/form/div[5]/button[1]'
  #   username_input.send_keys("admin")
  #   password_input.send_keys("admin")
  #   time.sleep(2)
  #   login_button.click()

  #   time.sleep(5)

  #   if driver.find_element(By.XPATH, new_password):
  #     new_password_input = driver.find_element(By.XPATH, new_password)
  #     confirm_password_input = driver.find_element(By.XPATH, confirm_password)
  #     new_password_input.send_keys("admin")
  #     confirm_password_input.send_keys("admin")
  #     time.sleep(2)
  #     input("Press Enter to continue...")
  #     botton_confirm_password = driver.find_element(By.XPATH, confirm_password_button)
  #     botton_confirm_password.click()
  #     time.sleep(5)

  # finally:
  #   driver.quit()
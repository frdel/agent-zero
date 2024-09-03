from python.helpers.strings import calculate_valid_match_lengths

# first = b'python3 -c \'from selenium import webdriver\nfrom selenium.webdriver.chrome.service import Service\nfrom webdriver_manager.chrome import ChromeDriverManager\nimport time\n\n# Set up the Chromium WebDriver\noptions = webdriver.ChromeOptions()\noptions.add_argument(\'"\'"\'--headless\'"\'"\')  # Run in headless mode\noptions.add_argument(\'"\'"\'--no-sandbox\'"\'"\')\noptions.add_argument(\'"\'"\'--disable-dev-shm-usage\'"\'"\')\n\n# Specify the correct version of ChromeDriver\nservice = Service(\'"\'"\'/root/.wdm/drivers/chromedriver/linux64/128.0.6613.113/chromedriver\'"\'"\')\ndriver = webdriver.Chrome(service=service, options=options)\n\n# Navigate to the LinkedIn profile\nurl = \'"\'"\'https://www.linkedin.com/in/jan-tomasek/\'"\'"\'\ndriver.get(url)\n\n# Wait for the page to load\ntime.sleep(5)\n\n# Save the page source to a file\nwith open(\'"\'"\'jan_tomasek_linkedin.html\'"\'"\', \'"\'"\'w\'"\'"\', encoding=\'"\'"\'utf-8\'"\'"\') as file:\n    file.write(driver.page_source)\n\n# Close the WebDriver\ndriver.quit()\'\n'
first = b'https://www.linkedin.com/in/jan-tomasek/\'"\'"\'\ndriver.get(url)\n\n# Wait for the page to load\ntime.sleep(5)\n\n# Save the page source to a file\nwith open(\'"\'"\'jan_tomasek_linkedin.html\'"\'"\', \'"\'"\'w\'"\'"\', encoding=\'"\'"\'utf-8\'"\'"\') as file:\n    file.write(driver.page_source)\n\n# Close the WebDriver\ndriver.quit()\'\n'

# second = b'python3 -c \'from selenium import webdriver\r\n\x1b[?2004l\r\x1b[?2004h> from selenium.webdriver.chrome.service import Service\r\n\x1b[?2004l\r\x1b[?2004h> from webdriver_manager.chrome import ChromeDriverManager\r\n\x1b[?2004l\r\x1b[?2004h> import time\r\n\x1b[?2004l\r\x1b[?2004h> \r\n\x1b[?2004l\r\x1b[?2004h> # Set up the Chromium WebDriver\r\n\x1b[?2004l\r\x1b[?2004h> options = webdriver.ChromeOptions()\r\n\x1b[?2004l\r\x1b[?2004h> options.add_argument(\'"\'"\'--headless\'"\'"\')  # Run in headless mode\r\n\x1b[?2004l\r\x1b[?2004h> options.add_argument(\'"\'"\'--no-sandbox\'"\'"\')\r\n\x1b[?2004l\r\x1b[?2004h> options.add_argument(\'"\'"\'--disable-dev-shm-usage\'"\'"\')\r\n\x1b[?2004l\r\x1b[?2004h> \r\n\x1b[?2004l\r\x1b[?2004h> # Specify the correct version of ChromeDriver\r\n\x1b[?2004l\r\x1b[?2004h> service = Service(\'"\'"\'/root/.wdm/drivers/chromedriver/linux64/128.0.6613.113/chromedriver\'"\'"\')\r\n\x1b[?2004l\r\x1b[?2004h> driver = webdriver.Chrome(service=service, options=options)\r\n\x1b[?2004l\r\x1b[?2004h> \r\n\x1b[?2004l\r\x1b[?2004h> # Navigate to the LinkedIn profile\r\n\x1b[?2004l\r\x1b[?2004h> url = \'"\'"\'https://www.linkedin.com/in/jan-tomasek/\'"\'"\'\r\n\x1b[?'
second = b'https://www.linkedin.com/in/jan-tomasek/\'"\'"\'\r\n\x1b[?'

trim_com, trim_out = calculate_valid_match_lengths(
    first, second, deviation_threshold=8, deviation_reset=2, 
    ignore_patterns = [
        rb'\x1b\[\?\d{4}[a-zA-Z](?:> )?',  # ANSI escape sequences
        rb'\r',                            # Carriage return
        rb'>\s',                             # Greater-than symbol
    ],
    debug=True)

if(trim_com > 0 and trim_out > 0):
    sec_tr = second[:trim_out]
else: sec_tr = "original"

print(sec_tr)
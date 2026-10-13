# Starting of the program
############## ! Imports ##############
# ? Selenium --> For interacting with the web browser
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchFrameException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from pathlib import Path
from urllib.parse import urlsplit


# ? Time --> For pausing the program
from time import sleep

# ? Questionary --> For beautiful command line prompts
from questionary import Style, select, text


# ? OS --> For clearing the screen
from os import system, name as OSNAME

# ? Rich --> For a box and loading bar
from rich import print
from rich.console import Console

console = Console()
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    TextColumn,
)
from rich.align import Align


############## ! Functions ##############
# * Initializing selenium with Chrome settings
def setSelenium():
    global allNames, chromeOptions
    chromeOptions = ChromeOptions()
    chromeOptions.add_experimental_option("detach", True)
    chromeOptions.add_argument("--lang=en-US")
    # Keep these sessions' microphone and camera off. Clicking an audio
    # toggle twice would restore its original state, not reliably mute it.
    prefs = {
        "profile.default_content_setting_values.media_stream_mic": 2,
        "profile.default_content_setting_values.media_stream_camera": 2,
        "intl.accept_languages": "en-US,en",
    }
    chromeOptions.add_experimental_option("prefs", prefs)
    # ? Reading all the names from 'names.txt'
    names_path = Path(__file__).resolve().with_name("names.txt")
    allNames = [
        name.strip()
        for name in names_path.read_text(encoding="utf-8-sig").splitlines()
        if name.strip()
    ]
    if not allNames:
        raise ValueError("names.txt must contain at least one non-empty name.")


PAGE_TIMEOUT = 60
NAME_FIELD = (By.ID, "input-for-name")
BROWSER_JOIN_LINK = (
    By.XPATH,
    "//*[self::a or self::button or @role='button']"
    "[contains(translate(normalize-space(.), "
    "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
    "'join from your browser')]",
)


def findInPageOrFrames(driver, locator, max_depth=2):
    """Find a visible, enabled control, leaving its frame selected.

    Every retry starts at the top-level page. Do not assume that the first
    iframe is Zoom's form: consent or verification frames can come first.
    """
    driver.switch_to.default_content()

    def search(depth):
        for element in driver.find_elements(*locator):
            if element.is_displayed() and element.is_enabled():
                return element
        if depth < max_depth:
            for frame in driver.find_elements(By.TAG_NAME, "iframe"):
                driver.switch_to.frame(frame)
                element = search(depth + 1)
                if element:
                    return element
                driver.switch_to.parent_frame()
        return False

    try:
        return search(0)
    except (StaleElementReferenceException, NoSuchFrameException):
        # Zoom may replace its form/iframe while it is loading.
        driver.switch_to.default_content()
        return False


# * Clicking join from browser on the page
def clickJoinFromBrowser(driver, timeout=PAGE_TIMEOUT):
    """Follow the browser link, or accept an already-open web join form."""
    clicked_browser_link = False

    def preview_ready(browser):
        nonlocal clicked_browser_link
        name_field = findInPageOrFrames(browser, NAME_FIELD)
        if name_field:
            return name_field
        if not clicked_browser_link:
            browser_link = findInPageOrFrames(browser, BROWSER_JOIN_LINK)
            if browser_link:
                try:
                    browser_link.click()
                    clicked_browser_link = True
                except (ElementClickInterceptedException, StaleElementReferenceException):
                    # Retry if the page is still changing or a prompt covers it.
                    pass
        return False

    return WebDriverWait(driver, timeout, poll_frequency=0.25).until(
        preview_ready,
        message="Zoom's browser join form did not become available.",
    )


# * Function if user selected ID and Password method
def idPass(id=None, password=None):
    # ? If ID is not provided
    if id == None:
        id = text("Enter Zoom Meeting ID:", style=minimalStyle).ask().replace(' ', '')

    else:
        # ? If ID is provided
        id = int(str(id.replace(" ", "")))

    # ? If password is not provided
    if password == None:
        password = text("Enter Zoom Meeting Password:", style=minimalStyle).ask()

    # ? Creating a loop for all the names provided
    for name in allNames:

        driver = webdriver.Chrome(options=chromeOptions)
        # ? Opening the website
        driver.get(
            f"https://zoom.us/wc/{id}/join?from=join&_x_zm_rtaid=ws81SA1uSGuB2O6_Sekbbg.1690523013218.d0e8a870b0195ee064d41de484bdd657&_x_zm_rhtaid=508"
        )
        sleep(0.5)
        driver.switch_to.frame(driver.find_element(By.TAG_NAME,"iframe"))
        # ? Entering password
        pwd = driver.find_element(By.ID, "input-for-pwd")
        pwd.clear()
        pwd.send_keys(password)
        
        # ? Entering name
        user = driver.find_element(By.ID, "input-for-name")
        user.clear()
        user.send_keys(name)

        # Microphone and camera are disabled by the Chrome preferences.
        user.send_keys(Keys.RETURN)


# * Function if user selected link method
def link(link=None):
    # ? If link is not provided
    if link is None:
        link = text("Enter Zoom Meeting Link:", style=minimalStyle).ask()
    if not link or not link.strip():
        print("No meeting link entered.")
        return
    link = link.strip()
    try:
        parsed = urlsplit(link)
        valid_link = parsed.scheme in ("https", "http") and bool(parsed.hostname)
    except ValueError:
        valid_link = False
    if not valid_link:
        print("Paste the complete meeting URL, starting with https://.")
        return

    # Keep the supplied URL, including its encoded pwd parameter, unchanged.
    passcode = None
    print(
        "If Chrome asks to open the Zoom app, click Cancel. "
        "Complete any sign-in, verification, or consent prompts in the browser."
    )

    for name in allNames:
        try:
            driver = webdriver.Chrome(options=chromeOptions)
            driver.set_page_load_timeout(PAGE_TIMEOUT)
            driver.get(link)
            user = clickJoinFromBrowser(driver)
            user.clear()
            user.send_keys(name)

            # Some invitations ask for a passcode on the name form. A URL's
            # encoded pwd value is not a plain passcode; never type it here.
            for field in driver.find_elements(By.ID, "input-for-pwd"):
                if field.is_displayed() and field.is_enabled() and not field.get_attribute("value"):
                    if passcode is None:
                        passcode = text(
                            "Zoom is asking for the meeting passcode:",
                            style=minimalStyle,
                        ).ask()
                    if not passcode:
                        print("No passcode entered. Continue in the open browser.")
                        return
                    field.send_keys(passcode)

            # Wait for the visible Join button in the same frame as the form.
            # Do not target a generated CSS class or an anchor's list position.
            join_locator = (
                By.XPATH,
                "//button[translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='join']"
                " | //input[@type='submit' and "
                "translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='join']",
            )

            def submit_join(browser):
                try:
                    for button in browser.find_elements(*join_locator):
                        if button.is_displayed() and button.is_enabled():
                            button.click()
                            return True
                except (ElementClickInterceptedException, StaleElementReferenceException):
                    pass
                return False

            WebDriverWait(driver, PAGE_TIMEOUT, poll_frequency=0.25).until(submit_join)
            console.print(
                f"Submitted the join form for {name}. Check the browser for "
                "admission, a waiting room, or further prompts.",
                markup=False,
            )
        except TimeoutException:
            print(
                "Timed out waiting for Zoom's browser join form or Join button. "
                "Check the open Chrome window: cancel any Open Zoom app prompt, "
                "complete sign-in/verification/consent, and confirm that the host "
                "allows Join from your browser. Stopped before opening more sessions."
            )
            return
        except WebDriverException as exc:
            console.print(f"Browser error: {exc.msg}", markup=False)
            print("Stopped. Check the open browser before trying again.")
            return


# * Loading Bar
def StatBar(time: float, desc: str):
    progress_bar = Progress(
        TextColumn(f"{desc} "),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    )
    with progress_bar as p:
        for i in p.track(range(100), description=desc):
            sleep(time / 100)
    sleep(0.5)


############## ! Printing Options ##############
if __name__ == "__main__":
    setSelenium()
    system("clear" if OSNAME == 'posix' else "cls")
    Align.center(
        StatBar(2, desc="[cyan]Loading Zoom Bomber"), vertical="middle"
    )
    system("clear" if OSNAME == 'posix' else "cls")
    console.print(
        Panel.fit("[bold italic #77DDD4]Zoom Bomber", padding=(0, 22))
    )
    minimalStyle = Style(
        [
            ("answer", "fg:#FFFFFF italic"),  # ? White
            ("question", "fg:#FFFFFF bold"),  # ? White
            ("pointer", "fg:#00FFFF bold"),  # ? Cyan
            ("highlighted", "fg:#FFFFFF"),  # ? White
            ("selected", "fg:#A9A9A9"),  # ? Grey
            ("qmark", "fg:#77DD77"),  # ? Green
        ]
    )
    userSelect = select(
        "Choose a way to bomb your meetings: ", ["ID/Pass", "Link"], style=minimalStyle
    ).ask()
    sleep(0.5)
    system("clear" if OSNAME == 'posix' else "cls")
    if userSelect == "ID/Pass":
        idPass()
    elif userSelect == "Link":
        link()
    else:
        print("Unknown error, please restart the program")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import base64
import os

options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=2000,2000")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(options=options)
try:
    url = "https://www.scribd.com/embeds/798692378/content"
    print(f"Loading {url}...")
    driver.get(url)
    time.sleep(5)
    
    # Hide cookie dialogs
    driver.execute_script(
        """
        document.querySelectorAll('[class*="cookie"], [class*="consent"]').forEach(el => el.remove());
        """
    )
    
    # Scroll through pages
    print("Scrolling to load all pages...")
    for _ in range(3):
        pages = driver.find_elements("css selector", ".outer_page")
        for p in pages:
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", p)
            time.sleep(0.1)
            
    pages = driver.find_elements("css selector", ".outer_page")
    print(f"Total pages loaded: {len(pages)}")
    
    # prepare for print
    driver.execute_script(
        """
        const toolbarTop = document.querySelector('.toolbar_top');
        if (toolbarTop) toolbarTop.remove();
        const toolbarBottom = document.querySelector('.toolbar_bottom');
        if (toolbarBottom) toolbarBottom.remove();
        
        document.querySelectorAll('.document_scroller').forEach((element) => {
            element.setAttribute('data-scribd-print-root', 'true');
            element.style.position = 'static';
            element.style.overflow = 'visible';
            element.style.maxHeight = 'none';
            element.style.height = 'auto';
            element.style.margin = '0';
            element.style.padding = '0';
        });
        """
    )
    
    # Dynamic print styles injection
    driver.execute_script(
        """
        const existing = document.getElementById('scribd-print-styles');
        if (existing) {
            existing.remove();
        }

        const style = document.createElement('style');
        style.id = 'scribd-print-styles';
        
        let cssText = `
            [class*="cookie"], [class*="consent"], [class*="osano-cm"], [id*="osano"] {
                display: none !important;
                visibility: hidden !important;
            }

            [data-scribd-print-root="true"],
            .document_scroller {
                position: static !important;
                overflow: visible !important;
                height: auto !important;
                max-height: none !important;
                margin: 0 !important;
                padding: 0 !important;
            }

            @media print {
                html, body {
                    margin: 0 !important;
                    padding: 0 !important;
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                }

                .toolbar_top, .toolbar_bottom {
                    display: none !important;
                }

                [data-scribd-print-root="true"],
                .document_scroller {
                    position: static !important;
                    overflow: visible !important;
                    height: auto !important;
                    max-height: none !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                .outer_page {
                    margin: 0 !important;
                    break-inside: avoid !important;
                    page-break-inside: avoid !important;
                    break-after: page !important;
                    page-break-after: always !important;
                }

                .outer_page:last-of-type {
                    break-after: auto !important;
                    page-break-after: auto !important;
                }
            }
        `;
        
        // Generate individual @page rules for each .outer_page
        const outerPages = Array.from(document.querySelectorAll('.outer_page'));
        outerPages.forEach((page, index) => {
            const rect = page.getBoundingClientRect();
            const widthInches = rect.width / 96;
            const heightInches = rect.height / 96;
            const pageName = `page_size_${index}`;
            
            cssText += `
                @page ${pageName} {
                    size: ${widthInches.toFixed(3)}in ${heightInches.toFixed(3)}in;
                    margin: 0;
                }
                
                @media print {
                    .outer_page:nth-of-type(${index + 1}) {
                        page: ${pageName} !important;
                    }
                }
            `;
        });

        style.textContent = cssText;
        document.head.appendChild(style);
        """
    )
    print("Injected dynamic print styles with nth-of-type selectors.")
    
    driver.execute_cdp_cmd("Emulation.setEmulatedMedia", {"media": "print"})
    driver.execute_script("window.scrollTo(0, 0);")
    
    # Save PDF using printToPDF with preferCSSPageSize = True
    print("Generating PDF...")
    pdf_options = {
        "landscape": False,
        "displayHeaderFooter": False,
        "printBackground": True,
        "scale": 1,
        "paperWidth": 8.5, # Ignored due to preferCSSPageSize
        "paperHeight": 11.0, # Ignored due to preferCSSPageSize
        "marginTop": 0,
        "marginBottom": 0,
        "marginLeft": 0,
        "marginRight": 0,
        "preferCSSPageSize": True,
    }
    
    result = driver.execute_cdp_cmd("Page.printToPDF", pdf_options)
    pdf_data = base64.b64decode(result["data"])
    filename = "zombie_spreads_dynamic_test.pdf"
    with open(filename, "wb") as f:
        f.write(pdf_data)
        
    print(f"Saved PDF to {filename}")
    size = os.path.getsize(filename) / (1024 * 1024)
    print(f"PDF size: {size:.2f} MB")
    
finally:
    driver.quit()

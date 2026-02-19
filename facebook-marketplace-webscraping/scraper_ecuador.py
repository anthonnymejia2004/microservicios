from splinter import Browser
from bs4 import BeautifulSoup as soup
import re
import pandas as pd
import time
import random
import os
import pickle
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

COOKIES_FILE = "fb_cookies.pkl"

def save_cookies(browser):
    print("Guardando sesión (cookies)...")
    pickle.dump(browser.driver.get_cookies(), open(COOKIES_FILE, "wb"))
    print("Sesión guardada exitosamente.")

def load_cookies(browser):
    if os.path.exists(COOKIES_FILE):
        print("Cargando sesión anterior...")
        cookies = pickle.load(open(COOKIES_FILE, "rb"))
        browser.visit("https://www.facebook.com") # Must be on domain to set cookies
        for cookie in cookies:
            try:
                browser.driver.add_cookie(cookie)
            except Exception as e:
                print(f"Error cargando cookie: {e}")
        print("Sesión cargada.")
        return True
    return False

def scrape_marketplace():
    print("Iniciando el scraper AVANZADO para Ecuador...")

    # Set up Splinter with webdriver_manager
    executable_path = ChromeDriverManager().install()
    os.environ["PATH"] += os.pathsep + os.path.dirname(executable_path)
    
    print("Abriendo navegador Chrome...")
    # Add arguments to make it less detectable and keep session better
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    
    browser = Browser('chrome', options=options, headless=False)

    # 1. Manage Login / Session
    session_loaded = load_cookies(browser)
    
    if not session_loaded:
        print("\n" + "="*60)
        print(" PRIMERA VEZ: INICIO DE SESIÓN MANUAL REQUERIDO")
        browser.visit("https://www.facebook.com/login")
        print("1. Inicia sesión en el navegador.")
        print("2. Si te pide autenticación en dos pasos, apruébala.")
        input("3. Cuando veas tu inicio de Facebook, presiona ENTER aquí...")
        save_cookies(browser)
    else:
        print("Sesión recuperada. Verificando acceso...")
        browser.visit("https://www.facebook.com")
        time.sleep(3)
        # Check if actually logged in (simple check)
        if "login" in browser.url:
            print("La sesión guardada expiró. Por favor inicia sesión de nuevo.")
            input("Presiona ENTER cuando hayas iniciado sesión...")
            save_cookies(browser)

    # 2. Construct Query
    city = "cuenca" 
    base_url = f"https://www.facebook.com/marketplace/{city}/search?"
    
    # Relaxed parameters for better testing
    # Removed min/max price strictness to ensure we find SOMETHING first
    min_price = 70
    max_price = 1500
    query = "Samsung Galaxy"
    
    url = f"{base_url}minPrice={min_price}&maxPrice={max_price}&query={query}&exact=false"
    
    print(f"Buscando: {query} en {city}...")
    browser.visit(url)
    time.sleep(5) # Initial load wait

    # 3. Scroll
    scroll_count = 3
    for i in range(scroll_count):
        print(f"Haciendo scroll {i+1}/{scroll_count}...")
        browser.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

    print("Analizando resultados...")
    html = browser.html
    market_soup = soup(html, 'html.parser')

    # Try to find items. Facebook classes change, but aria-labels often stay.
    scraped_data = []

    # 4. Analizar el contenido HTML
    print("Analizando resultados...")
    html = browser.html
    soup_obj = soup(html, 'html.parser')

    # Intentar varios selectores comuns de Marketplace
    # Selector de artículos (puede variar, Facebook cambia esto a menudo)
    # Buscamos elementos que tengan precio y título
    
    # Estrategia: Buscar contenedores que tengan texto con signo de dólar
    items = soup_obj.find_all('div', class_=lambda x: x and 'x1lliihq' in x) # Clase muy genérica, filtraremos después
    
    count = 0
    print("\n--- RESULTADOS ENCONTRADOS ---")
    
    # Estrategia alternativa: Buscar por texto visible
    # Facebook ofusca las clases, así que buscamos patrones de texto
    all_text_elements = soup_obj.find_all(string=True)
    
    current_item = {}
    
    # Iteramos por elementos de texto para encontrar patrones de precio
    for element in all_text_elements:
        text = element.strip()
        if not text:
            continue
            
        # Si parece un precio ($1.234 o $ 1,234)
        if re.match(r'^\$\s?[\d,.]+', text):
            # Asumimos que el título está cerca (en los elementos anteriores o padres)
            # Simplificación: Guardamos este precio y buscamos el texto más largo cercano como título
            price_str = text
            parent = element.parent
            
            # Subir niveles para encontrar el contenedor de la tarjeta
            card = parent
            for _ in range(5):
                if card.parent:
                    card = card.parent
            
            # Extraer todo el texto de la tarjeta
            card_text = card.get_text(separator=' | ', strip=True)
            
            # Limpieza básica para extraer "Título" y "Ubicación"
            parts = card_text.split('|')
            title = "Desconocido"
            location_found = "Ecuador"
            
            # Regex para detectar formato "Ciudad, Provincia" (ej: "Quito, P", "Guayaquil, G")
            # \w incluye caracteres con tilde en Python 3 regex default? No siempre si no se usa Flag.
            # Mejor usamos rango explícito para asegurar.
            location_pattern = re.compile(r'^[a-zA-Z\u00C0-\u00FF\s]+,\s*[A-Z]{1,2}$')

            # Clasificar las partes
            potential_titles = []
            
            # Debug: ver qué partes estamos analizando
            # print(f"DEBUG partes partes: {parts}") 

            for part in parts:
                p = part.strip()
                if not p: continue
                if '$' in p: continue # Es el precio
                if 'pago' in p.lower(): continue # Es info de pago
                
                # Chequear si es ubicación
                is_loc = False
                if location_pattern.match(p):
                    location_found = p
                    is_loc = True
                elif any(city.lower() == p.lower() for city in ['quito', 'guayaquil', 'cuenca', 'ambato', 'loja', 'riobamba', 'manta', 'machala', 'santo domingo', 'esmeraldas']):
                    location_found = p
                    is_loc = True
                
                if not is_loc and len(p) > 2: # Si es texto y no es ubicación ni precio
                    potential_titles.append(p)
            
            # El título suele ser el candidato más largo o el primero viable
            if potential_titles:
                 # Preferimos el que NO sea la ubicación si se coló
                 clean_titles = [t for t in potential_titles if t != location_found]
                 if clean_titles:
                     title = clean_titles[0]
                 else:
                     # Si todo lo que había era la ubicación, entonces no hay título real
                     title = "Título no detectado"
            else:
                 title = "Título no detectado"

            try:
                # Limpiar precio para cálculo
                price_clean = re.sub(r'[^\d]', '', price_str)
                price_val = float(price_clean) if price_clean else 0
            except:
                price_val = 0

            print(f"Artículo: {title} - Precio: {price_str}")
            
            scraped_data.append({
                "Titulo": title,
                "Precio_Texto": price_str,
                "Precio_Numerico": price_val,
                "Ubicacion": location_found,
                "Texto_Completo": card_text[:100] + "..." # Guardar un poco de contexto
            })
            count += 1
            if count >= 30: # Límite para demo
                break
    
    if count == 0:
        print("⚠️ No se detectaron artículos con estructura estándar. Intentando búsqueda genérica...")
        # Fallback ultra simple
        results = soup_obj.find_all('span', string=re.compile(r'\$'))
        
        # Regex para ubicación (reutilizado)
        location_pattern = re.compile(r'^[a-zA-Z\u00C0-\u00FF\s]+,\s*[A-Z]{1,2}$')

        for res in results:
            try:
                price = res.text.strip()
                title = "Producto sin título"
                location_found = "Desconocida"
                
                # Buscar elementos anteriores candidatos
                # Buscamos hasta 3 elementos hacia atrás para ver si uno es título y otro ubicación
                current = res
                for _ in range(5):
                    prev = current.find_previous('span', string=lambda x: x and len(x) > 3)
                    if not prev:
                        break
                    
                    text_prev = prev.text.strip()
                    if '$' in text_prev: # Es otro precio
                        current = prev
                        continue
                        
                    # Chequear si es ubicación
                    if location_pattern.match(text_prev) or any(city.lower() == text_prev.lower() for city in ['quito', 'guayaquil', 'cuenca', 'ambato', 'loja', 'riobamba', 'manta', 'machala', 'santo domingo', 'esmeraldas']):
                        location_found = text_prev
                    # Chequear si es título (largo y no es la ubicación que acabamos de encontrar)
                    elif len(text_prev) > 10 and text_prev != location_found:
                         title = text_prev
                         # Si encontramos título, paramos (asumimos que ubicación estaba antes o después, pero ya tenemos algo)
                         # A veces la ubicación está ANTES del título, a veces DESPUÉS.
                         # Si ya tenemos ubicación, genial. Si no, seguimos buscando.
                    
                    current = prev
                
                # Si el título que encontramos resulta ser igual a la ubicación (caso borde), lo limpiamos
                if title == location_found:
                    title = "Título no detectado"

                print(f"Posible Artículo: {title} ({price}) - Loc: {location_found}")
                
                price_clean = re.sub(r'[^\d]', '', price)
                price_val = float(price_clean) if price_clean else 0

                scraped_data.append({
                    "Titulo": title,
                    "Precio_Texto": price,
                    "Precio_Numerico": price_val,
                    "Ubicacion": location_found,
                    "Texto_Completo": "Captura genérica (Fallback)"
                })
                count += 1
            except Exception as e:
                # print(f"Error en fallback: {e}")
                continue

    # --- METRICAS Y EXPORTACION ---
    if scraped_data:
        print(f"\n✅ Se encontraron {len(scraped_data)} artículos.")
        
        # Calcular métricas
        prices = [d['Precio_Numerico'] for d in scraped_data if d['Precio_Numerico'] > 0]
        if prices:
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            
            print("\n📊 --- MÉTRICAS DEL MERCADO --- 📊")
            print(f"Total Items: {len(scraped_data)}")
            print(f"Precio Promedio: ${avg_price:,.2f}")
            print(f"Precio Mínimo: ${min_price:,.2f}")
            print(f"Precio Máximo: ${max_price:,.2f}")
        
        # Guardar a CSV
        try:
            import pandas as pd
            df = pd.DataFrame(scraped_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"resultados_marketplace_{timestamp}.csv"
            df.to_csv(filename, index=False, encoding='utf-8-sig') # utf-8-sig para Excel
            print(f"\n💾 Datos guardados exitosamente en: {filename}")
            print("   (Puedes abrir este archivo en Excel para ver la tabla completa)")
        except ImportError:
            print("\n⚠️ Pandas no instalado, guardando CSV manual...")
            import csv
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"resultados_marketplace_{timestamp}.csv"
            keys = scraped_data[0].keys()
            with open(filename, 'w', newline='', encoding='utf-8-sig') as output_file:
                dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(scraped_data)
            print(f"\n💾 Datos guardados exitosamente en: {filename}")

        browser.driver.save_screenshot('resultados_exitosos.png')
        print("Captura guardada como 'resultados_exitosos.png'")
        
    else:
        print("\n❌ No se encontró nada. Posiblemente la estructura de Facebook cambió o detectaron el bot.")
        browser.driver.save_screenshot('debug_no_results.png')
        print("Captura de debug guardada como 'debug_no_results.png'")

    print("Cerrando navegador...")
    # browser.quit() 
    print("El navegador quedará abierto para que inspecciones. Ciérralo manualmente.")

if __name__ == "__main__":
    scrape_marketplace()

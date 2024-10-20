from fastapi import FastAPI, HTTPException
import asyncio
from aiohttp import ClientSession
from bs4 import BeautifulSoup
import sqlite3
from pydantic import BaseModel,EmailStr
from typing import List, Dict
import pandas as pd
from collections import Counter 
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base



app = FastAPI()
#headers = {
#    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
#}

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15"
}


conn = sqlite3.connect('products.db')
c = conn.cursor()

# Pydantic model for the input
class EmailInput(BaseModel):
    email:EmailStr

# c.execute('''
#     CREATE TABLE IF NOT EXISTS products (
#         product_id INTEGER PRIMARY KEY AUTOINCREMENT,
#         product TEXT,
#         name TEXT,
#         price TEXT,
#         url TEXT,
#         UNIQUE(product, name)
#     )
# ''')
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id TEXT ,                  
        search_term TEXT
    )
''')
c.execute('''
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product TEXT,
        name TEXT,
        price TEXT,
        url TEXT,
        user_id TEXT,                         
        FOREIGN KEY(user_id) REFERENCES users(user_id)    )
''')
c.execute('''
    CREATE TABLE IF NOT EXISTS user_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        Email TEXT)
''')
conn.commit()

class Product(BaseModel):
    product: str
    results: List[Dict[str, str]]

async def fetch(url, session):
    async with session.get(url, headers=headers) as response:
        return await response.text()



# async def scrape_amazon(product, session):
#     url = f"https://www.amazon.com/s?k={product}"
#     html = await fetch(url, session)
#     soup = BeautifulSoup(html, 'html.parser')
#     items = []
#     for result in soup.find_all('div', {'data-component-type': 's-search-result'}):
#         name = result.find('span', {'class': 'a-size-medium'}).text.strip()
#         price = result.find('span', {'class': 'a-offscreen'}).text.strip() if result.find('span', {'class': 'a-offscreen'}) else 'Price not found'
#         link = result.find('a', {'class': 'a-link-normal'})['href'] if result.find('a', {'class': 'a-link-normal'}) else 'URL not found'
#         img = result.find('img', {'class': 's-image'})['src'] if result.find('img', {'class': 's-image'}) else 'Image not found'
#         items.append({
#             'name': name,
#             'price': price,
#             'url': "https://www.amazon.com" + link,
#             'platform': 'Amazon',
#             'image_url': img
#         })
#     return items

async def scrape_ebay(product, session):
    url = f"https://www.ebay.com/sch/i.html?_nkw={product}"
    html = await fetch(url, session)
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for result in soup.find_all('div', {'class': 's-item__info'}):
        name = result.find('h3', {'class': 's-item__title'}).text.strip() if result.find('h3', {'class': 's-item__title'}) else product
        price = result.find('span', {'class': 's-item__price'}).text.strip() if result.find('span', {'class': 's-item__price'}) else 'Price not found'
        link = result.find('a', {'class': 's-item__link'})['href'] if result.find('a', {'class': 's-item__link'}) else 'URL not found'
        img = result.find('img', {'class': 's-item__image-img'})['src'] if result.find('img', {'class': 's-item__image-img'}) else 'Image not found'
        items.append({
            'name': name,
            'price': price,
            'url': link,
            'platform': 'eBay',
            'image_url': img
        })
    return items

async def search_product(product: str, user_id: str):
    async with ClientSession() as session:
        # Scrape eBay for the product
        ebay_task = scrape_ebay(product, session)
        ebay_items = await ebay_task
        results = ebay_items

        # Check if the user_id exists in the 'users' table
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user_exists = c.fetchone()

        if not user_exists:
            return {"user not found"}
            # User doesn't exist, insert new user
            # c.execute('INSERT INTO users (user_id, search_term) VALUES (?, ?)', (user_id, product))
            # conn.commit()

            # # Insert products scraped from eBay into products table
            # for result in results:
            #     c.execute('INSERT INTO products (product, name, price, url, user_id) VALUES (?, ?, ?, ?, ?)', 
            #               (product, result['name'], result['price'], result['url'], user_id))
            #     conn.commit()

        else:
            # User exists, check if the product already exists for this user in the search_term
            c.execute('SELECT * FROM users WHERE user_id = ? AND search_term = ?', (user_id, product))
            product_exists_in_search = c.fetchone()

            if not product_exists_in_search:
                # Product doesn't exist for this user, insert a new record for the new product search term
                c.execute('INSERT INTO users (user_id, search_term) VALUES (?, ?)', (user_id, product))
                conn.commit()

                # Insert the new product into the products table
                for result in results:
                    c.execute('INSERT INTO products (product, name, price, url, user_id) VALUES (?, ?, ?, ?, ?)', 
                              (product, result['name'], result['price'], result['url'], user_id))
                    conn.commit()

            else:
                # Product exists for this user, update the existing products for the same product and user_id
                c.execute('DELETE FROM products WHERE product = ? AND user_id = ?', (product, user_id))
                conn.commit()

                # Insert the updated results for the same product
                for result in results:
                    c.execute(''' UPDATE products SET price = ?, url = ? WHERE product = ? AND name = ? AND user_id = ? ''', 
                              (result['price'], result['url'], product, result['name'], user_id))
                    conn.commit()

        return results


# async def search_product(product: str, user_id: str):
#     async with ClientSession() as session:
#         # Scrape eBay for the product
#         ebay_task = scrape_ebay(product, session)
#         ebay_items = await ebay_task
#         results = ebay_items

#         # Check if the user_id exists in the 'users' table
#         c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
#         user_exists = c.fetchone()

#         # if not user_exists:
#         #     # User doesn't exist, insert new user
#         #     c.execute('INSERT INTO users (user_id, search_term) VALUES (?, ?)', (user_id, product))
#         #     conn.commit()

#         #     # Insert products scraped from eBay into products table
#         #     for result in results:
#         #         c.execute('INSERT INTO products (product, name, price, url, user_id) VALUES (?, ?, ?, ?, ?)', 
#         #                   (product, result['name'], result['price'], result['url'], user_id))
#         #         conn.commit()

#         # else:
#             # User exists, check if the product already exists for this user in the search_term
#         c.execute('SELECT * FROM users WHERE user_id = ? AND search_term = ?', (user_id, product))
#         product_exists_in_search = c.fetchone()

#         if not product_exists_in_search:
#                 # Product doesn't exist for this user, insert a new record for the new product search term
#             c.execute('INSERT INTO users (user_id, search_term) VALUES (?, ?)', (user_id, product))
#             conn.commit()
#             # Insert the new product into the products table
#             for result in results:
#                 c.execute('INSERT INTO products (product, name, price, url, user_id) VALUES (?, ?, ?, ?, ?)', 
#                 (product, result['name'], result['price'], result['url'], user_id))
#                 conn.commit()

#         else:
#             # Product exists for this user, update the existing products for the same product and user_id
#             c.execute('DELETE FROM products WHERE product = ? AND user_id = ?', (product, user_id))
#             conn.commit()
#             # Insert the updated results for the same product
#             for result in results:
#                 c.execute(''' UPDATE products SET price = ?, url = ? WHERE product = ? AND name = ? AND user_id = ? ''', 
#                 (result['price'], result['url'], product, result['name'], user_id))
#                 conn.commit()

#         return results

# @app.post("/catagory_find/")
# async def catagory_of_product(product: str):
#     from fastapi import FastAPI

async def category_of_product(product: str):
    categories = {
        "Food": ["Fruits", "Pizza", "Burgers", "Rice", "Pasta", "Sushi"],
        "Electronics": ["Smartphones", "Laptops", "Headphones", "Cameras", "Tablets", "Smartwatches"],
        "Clothing": ["Shirts", "Jeans", "Jackets", "Shoes", "Hats", "Sweaters"],
        "Books": ["Fiction", "Non-fiction", "Fantasy", "Biography", "Science Fiction", "Self-Help"],
        "Furniture": ["Sofas", "Chairs", "Tables", "Beds", "Wardrobes", "Desks"],
        "Beauty": ["Skincare", "Makeup", "Haircare", "Fragrance", "Nail Care", "Body Care"],
        "Toys": ["Action Figures", "Board Games", "Dolls", "Educational Toys", "Video Games", "Puzzles"],
        "Sports": ["Football", "Basketball", "Tennis", "Cycling", "Swimming", "Running Gear"],
        "Automotive": ["Car Accessories", "Motorcycles", "Car Parts", "Tires", "Car Cleaning", "Helmets"],
        "Home Appliances": ["Washing Machines", "Refrigerators", "Microwaves", "Vacuum Cleaners", "Air Conditioners", "Ovens"],
        "Apple Products": ["iPhone", "iPad", "MacBook", "Apple Watch", "AirPods", "Apple TV"],
        "Accessories": ["Laptop Bags", "Phone Cases", "Headphone Cases", "Backpacks", "Chargers", "Screen Protectors"]
    }
    # Loop through each category and its list of products
    for category, products in categories.items():
        if product in products:
            return category
    return None

async def get_user_search_terms(user_id: int):
    conn = sqlite3.connect('products.db')  # Synchronous connect
    try:
        cursor = conn.cursor()   
         # Fetch all search terms for the user
        query = "SELECT user_id, search_term FROM users WHERE user_id = ?"
        cursor.execute(query, (user_id,))
        search_terms = cursor.fetchall()
        valid_search_terms = []
        for term in search_terms:
            if term[1] is None or term[1].strip() == "":  # Check if the search term is None or empty
               # Delete the entry with empty search_term
               delete_query = "DELETE FROM users WHERE user_id = ? AND search_term = ?"
               cursor.execute(delete_query, (user_id, term[1]))
               conn.commit()  # Commit the deletion
            else:
               valid_search_terms.append(term[1])  # Collect valid search terms
        return valid_search_terms  # Return only valid search terms
    finally:
       conn.close()

    # conn = sqlite3.connect('products.db')  # Synchronous connect
    # try:
    #     cursor = conn.cursor()
    #     query = "SELECT search_term FROM users WHERE user_id = ?"
    #     cursor.execute(query, (user_id,))
    #     search_terms = cursor.fetchall()
    #     return [term[0] for term in search_terms if term[0] is not None]
    # finally:
    #     conn.close()

@app.get("/recommendation_system/")
async def recommendation_system(user_id: str):
    search_terms = await get_user_search_terms(user_id)  # Await the asynchronous call
    if not search_terms:
        raise HTTPException(status_code=404, detail="User not found or no search terms available")

    # Count the frequency of each category from search terms
    category_counter = Counter()

    for term in search_terms:
        category = await category_of_product(term.strip())  # Await the category lookup
        if category:
            category_counter[category] += 1

    # Get the most common category
    most_common_category = category_counter.most_common(1)
    
    if most_common_category:
        results = await search_product(most_common_category[0][0],user_id)
        return results
    
    return {"message": "No valid categories found in search terms."}
# @app.get("/recommendation_system/")
# async def recommendation_system(user_id:str):
#     # c.execute('SELECT * FROM products')
#     # items = c.fetchall()
#     # results = [dict(item) for item in items]
#     # return {"items": results}
#     df = pd.read_sql_query('SELECT * FROM products', conn)
#     results = df.to_dict(orient="records")
#     num_rows = len(df)
#     #if num_rows >= 10:
#     # Get the last 10 products
#     last_10_products = [product['product'] for product in results[-10:]]
#     #print(last_10_products)
#     # else:
#     #     return {"your search history is not that enough"}
#     return {"items": results}
# async def search_product(product):
#     async with ClientSession() as session:
#         # amazon_task = scrape_amazon(product, session)
#         ebay_task = scrape_ebay(product, session)
#         # amazon_items = await amazon_task
#         ebay_items = await ebay_task
#         # return amazon_items + ebay_items
#         # c.execute('INSERT OR REPLACE INTO products VALUES (?, ?)', (product, str(ebay_items)))
#         # conn.commit()
#         return ebay_items

# @app.get("/search_by_user/")
# async def get_product(user_id:str):
#     return await get_user_search_terms(user_id)

@app.get("/search/")
async def get_product(product: str,user_id:str):
    results = await search_product(product,user_id)
    return results

@app.get("/users/")
async def users():
    c.execute('SELECT * FROM users')
    results = c.fetchall()
    return results


# Create the endpoint
@app.post("/get_user_id")
async def add_user_profile(email: EmailInput):
 
    # Check if the email exists in the user_profile table
    c.execute('SELECT * FROM user_profile WHERE Email = ?', (email.email,))
    user_profile = c.fetchone()
    
    if not user_profile:
        # Insert new email into user_profile and get the new user_id
        c.execute('INSERT INTO user_profile (Email) VALUES (?)', (email.email,))
        conn.commit()
        user_id = c.lastrowid  # The auto-incremented user_id from user_profile
        
        # Insert new user_id and search_term into users table
        c.execute('INSERT INTO users (user_id) VALUES (?)', (str(user_id)))
        conn.commit()
        
        return {"message": "New user profile and user created", "user_id": user_id}
    else:
        # raise HTTPException(status_code=400, detail="Email already exists")
        user_id = user_profile[0]
        return {"user_id": user_id}

# @app.get("/results/")
# async def get_results(product: str):
#     c.execute('SELECT name, price, url FROM products WHERE product = ?', (product,))
#     results = c.fetchall()
#     if not results:
#         return {"error": "No results found for this product"}
#     else:
#         return [{"name": result[0], "price": result[1], "url": result[2]} for result in results]

    
# @app.get("/products/")
# async def get_products():
#     c.execute('SELECT DISTINCT product FROM products')
#     products = c.fetchall()
#     return {"products": [product[0] for product in products]}


# @app.post("/store/")
# async def store_product(product: Product):
#     c.execute('INSERT OR REPLACE INTO products VALUES (?, ?)', (product.product, product.results))
#     conn.commit()
#     return {"status": "success"}


# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=10022)
#     conn.close()

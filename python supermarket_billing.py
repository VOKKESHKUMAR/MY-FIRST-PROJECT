import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
from datetime import datetime

# pyttsx3 is optional
try:
    import pyttsx3
    engine = pyttsx3.init()
except ImportError:
    engine = None


# =========================================================
# DATABASE
# =========================================================

conn = sqlite3.connect("supermarket.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL,
    gst REAL NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bills (
    invoice_no INTEGER,
    bill_date TEXT,
    item_code TEXT,
    item_name TEXT,
    quantity INTEGER,
    price REAL,
    gst REAL,
    total REAL
)
""")

# Insert default invoice number
cursor.execute(
    "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
    ("invoice_no", "1001")
)

# Add sample products if database is empty
cursor.execute("SELECT COUNT(*) FROM products")
if cursor.fetchone()[0] == 0:
    sample_products = [
        ("P001", "Rice", 60.00, 100, 5),
        ("P002", "Sugar", 45.00, 80, 5),
        ("P003", "Milk", 30.00, 50, 5),
        ("P004", "Bread", 40.00, 60, 5),
        ("P005", "Soap", 35.00, 75, 18),
        ("P006", "Shampoo", 120.00, 40, 18),
        ("P007", "Biscuits", 25.00, 100, 5),
        ("P008", "Cooking Oil", 150.00, 50, 5),
        ("P009", "Toothpaste", 80.00, 45, 18),
        ("P010", "Coffee", 90.00, 40, 5)
    ]

    cursor.executemany("""
        INSERT INTO products
        (code, name, price, stock, gst)
        VALUES (?, ?, ?, ?, ?)
    """, sample_products)

conn.commit()


# =========================================================
# MAIN WINDOW
# =========================================================

root = tk.Tk()
root.title("SUPERMARKET BILLING SYSTEM")
root.geometry("1100x700")
root.resizable(False, False)

# =========================================================
# VARIABLES
# =========================================================

cart = []

invoice_var = tk.StringVar()
code_var = tk.StringVar()
quantity_var = tk.StringVar(value="1")

item_name_var = tk.StringVar()
price_var = tk.StringVar()
gst_var = tk.StringVar()
stock_var = tk.StringVar()

subtotal_var = tk.StringVar(value="0.00")
gst_total_var = tk.StringVar(value="0.00")
grand_total_var = tk.StringVar(value="0.00")


# =========================================================
# VOICE FUNCTION
# =========================================================

def speak(text):
    if engine:
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass


# =========================================================
# INVOICE NUMBER
# =========================================================

def get_invoice_number():
    cursor.execute(
        "SELECT value FROM settings WHERE key='invoice_no'"
    )
    result = cursor.fetchone()

    if result:
        return int(result[0])

    return 1001


def increase_invoice_number():
    number = get_invoice_number() + 1

    cursor.execute(
        "UPDATE settings SET value=? WHERE key='invoice_no'",
        (str(number),)
    )

    conn.commit()


def update_invoice_display():
    invoice_var.set(str(get_invoice_number()))


# =========================================================
# CLEAR ITEM FIELDS
# =========================================================

def clear_item_fields():
    code_var.set("")
    quantity_var.set("1")
    item_name_var.set("")
    price_var.set("")
    gst_var.set("")
    stock_var.set("")


# =========================================================
# SEARCH PRODUCT
# =========================================================

def search_product(event=None):
    code = code_var.get().strip().upper()

    if not code:
        return

    cursor.execute("""
        SELECT name, price, stock, gst
        FROM products
        WHERE code=?
    """, (code,))

    product = cursor.fetchone()

    if product:
        name, price, stock, gst = product

        item_name_var.set(name)
        price_var.set(f"{price:.2f}")
        stock_var.set(str(stock))
        gst_var.set(f"{gst:.2f}%")

    else:
        item_name_var.set("")
        price_var.set("")
        stock_var.set("")
        gst_var.set("")


# =========================================================
# ADD ITEM TO BILL
# =========================================================

def add_item():
    code = code_var.get().strip().upper()

    if not code:
        messagebox.showwarning(
            "Warning",
            "Please enter an item code."
        )
        return

    try:
        quantity = int(quantity_var.get())

        if quantity <= 0:
            raise ValueError

    except ValueError:
        messagebox.showerror(
            "Invalid Quantity",
            "Please enter a valid quantity."
        )
        return

    cursor.execute("""
        SELECT name, price, stock, gst
        FROM products
        WHERE code=?
    """, (code,))

    product = cursor.fetchone()

    if not product:
        messagebox.showerror(
            "Item Not Found",
            "Item code does not exist."
        )
        return

    name, price, stock, gst = product

    if quantity > stock:
        messagebox.showerror(
            "Stock Error",
            f"Only {stock} units are available."
        )
        return

    # Check whether item already exists in cart
    for item in cart:

        if item["code"] == code:

            new_quantity = item["quantity"] + quantity

            if new_quantity > stock:
                messagebox.showerror(
                    "Stock Error",
                    f"Only {stock} units are available."
                )
                return

            item["quantity"] = new_quantity

            refresh_cart()
            clear_item_fields()
            calculate_total()
            return

    item = {
        "code": code,
        "name": name,
        "price": price,
        "quantity": quantity,
        "gst": gst
    }

    cart.append(item)

    refresh_cart()
    calculate_total()
    clear_item_fields()

    speak(f"{name} added to bill")


# =========================================================
# REFRESH BILL TABLE
# =========================================================

def refresh_cart():

    for row in bill_tree.get_children():
        bill_tree.delete(row)

    for item in cart:

        basic_amount = item["price"] * item["quantity"]

        gst_amount = basic_amount * item["gst"] / 100

        total = basic_amount + gst_amount

        bill_tree.insert(
            "",
            "end",
            values=(
                item["code"],
                item["name"],
                item["quantity"],
                f"{item['price']:.2f}",
                f"{item['gst']:.2f}%",
                f"{gst_amount:.2f}",
                f"{total:.2f}"
            )
        )


# =========================================================
# REMOVE ITEM
# =========================================================

def remove_item():

    selected = bill_tree.selection()

    if not selected:
        messagebox.showwarning(
            "Warning",
            "Please select an item to remove."
        )
        return

    index = bill_tree.index(selected[0])

    if 0 <= index < len(cart):
        cart.pop(index)

    refresh_cart()
    calculate_total()


# =========================================================
# CALCULATE TOTAL
# =========================================================

def calculate_total():

    subtotal = 0
    gst_total = 0

    for item in cart:

        amount = item["price"] * item["quantity"]

        gst_amount = amount * item["gst"] / 100

        subtotal += amount
        gst_total += gst_amount

    grand_total = subtotal + gst_total

    subtotal_var.set(f"{subtotal:.2f}")
    gst_total_var.set(f"{gst_total:.2f}")
    grand_total_var.set(f"{grand_total:.2f}")


# =========================================================
# GENERATE BILL
# =========================================================

def generate_bill():

    if not cart:
        messagebox.showwarning(
            "Empty Bill",
            "Please add items before generating the bill."
        )
        return

    invoice_no = get_invoice_number()

    now = datetime.now()

    date_text = now.strftime("%d-%m-%Y")
    time_text = now.strftime("%H:%M:%S")

    subtotal = float(subtotal_var.get())
    gst_total = float(gst_total_var.get())
    grand_total = float(grand_total_var.get())

    bill_text = ""

    bill_text += "=" * 60 + "\n"
    bill_text += "              SUPERMARKET BILL\n"
    bill_text += "=" * 60 + "\n"
    bill_text += f"Invoice No : {invoice_no}\n"
    bill_text += f"Date       : {date_text}\n"
    bill_text += f"Time       : {time_text}\n"
    bill_text += "-" * 60 + "\n"

    bill_text += (
        f"{'Code':<8}"
        f"{'Item':<18}"
        f"{'Qty':<6}"
        f"{'Price':<10}"
        f"{'GST':<8}"
        f"{'Total':<10}\n"
    )

    bill_text += "-" * 60 + "\n"

    # Update stock and save bill records
    for item in cart:

        amount = item["price"] * item["quantity"]

        gst_amount = amount * item["gst"] / 100

        total = amount + gst_amount

        bill_text += (
            f"{item['code']:<8}"
            f"{item['name'][:17]:<18}"
            f"{item['quantity']:<6}"
            f"{item['price']:<10.2f}"
            f"{item['gst']:<8.2f}"
            f"{total:<10.2f}\n"
        )

        # Reduce stock
        cursor.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE code=?
        """, (item["quantity"], item["code"]))

        # Save transaction
        cursor.execute("""
            INSERT INTO bills
            (
                invoice_no,
                bill_date,
                item_code,
                item_name,
                quantity,
                price,
                gst,
                total
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_no,
            now.strftime("%Y-%m-%d %H:%M:%S"),
            item["code"],
            item["name"],
            item["quantity"],
            item["price"],
            item["gst"],
            total
        ))

    conn.commit()

    bill_text += "-" * 60 + "\n"

    bill_text += f"Subtotal       : Rs. {subtotal:.2f}\n"
    bill_text += f"GST            : Rs. {gst_total:.2f}\n"
    bill_text += f"GRAND TOTAL     : Rs. {grand_total:.2f}\n"

    bill_text += "=" * 60 + "\n"
    bill_text += "             THANK YOU!\n"
    bill_text += "=" * 60 + "\n"

    # Create Bills folder
    os.makedirs("Bills", exist_ok=True)

    filename = f"Bills/Bill_{invoice_no}.txt"

    with open(filename, "w", encoding="utf-8") as file:
        file.write(bill_text)

    # Increase invoice number
    increase_invoice_number()
    update_invoice_display()

    # Show bill
    show_bill_window(bill_text)

    # Clear current bill
    cart.clear()
    refresh_cart()
    calculate_total()

    speak("Bill generated successfully")


# =========================================================
# SHOW BILL
# =========================================================

def show_bill_window(bill_text):

    bill_window = tk.Toplevel(root)

    bill_window.title("Generated Bill")
    bill_window.geometry("650x600")

    text = tk.Text(
        bill_window,
        font=("Courier New", 11),
        width=75,
        height=30
    )

    text.pack(
        padx=10,
        pady=10,
        fill="both",
        expand=True
    )

    text.insert("1.0", bill_text)

    text.config(state="disabled")

    def print_bill():

        try:

            filename = f"Bills/Bill_{get_invoice_number() - 1}.txt"

            os.startfile(filename, "print")

            messagebox.showinfo(
                "Print",
                "Bill sent to printer."
            )

        except Exception as e:

            messagebox.showerror(
                "Print Error",
                f"Unable to print bill.\n\n{e}"
            )

    tk.Button(
        bill_window,
        text="PRINT BILL",
        font=("Arial", 12, "bold"),
        width=18,
        command=print_bill
    ).pack(pady=10)


# =========================================================
# STOCK WINDOW
# =========================================================

def stock_window():

    window = tk.Toplevel(root)

    window.title("Stock Management")

    window.geometry("800x500")

    tree = ttk.Treeview(
        window,
        columns=(
            "code",
            "name",
            "price",
            "stock",
            "gst"
        ),
        show="headings"
    )

    tree.heading("code", text="Code")
    tree.heading("name", text="Item Name")
    tree.heading("price", text="Price")
    tree.heading("stock", text="Stock")
    tree.heading("gst", text="GST")

    tree.column("code", width=100)
    tree.column("name", width=200)
    tree.column("price", width=120)
    tree.column("stock", width=120)
    tree.column("gst", width=100)

    tree.pack(
        fill="both",
        expand=True,
        padx=10,
        pady=10
    )

    def load_stock():

        for row in tree.get_children():
            tree.delete(row)

        cursor.execute("""
            SELECT code, name, price, stock, gst
            FROM products
            ORDER BY code
        """)

        products = cursor.fetchall()

        for product in products:

            tree.insert(
                "",
                "end",
                values=(
                    product[0],
                    product[1],
                    f"{product[2]:.2f}",
                    product[3],
                    f"{product[4]:.2f}%"
                )
            )

    load_stock()


# =========================================================
# RESTOCK WINDOW
# =========================================================

def restock_window():

    window = tk.Toplevel(root)

    window.title("Restock Items")
    window.geometry("500x400")

    tk.Label(
        window,
        text="RESTOCK PRODUCT",
        font=("Arial", 18, "bold")
    ).pack(pady=15)

    frame = tk.Frame(window)
    frame.pack(pady=20)

    tk.Label(
        frame,
        text="Item Code:",
        font=("Arial", 12)
    ).grid(row=0, column=0, padx=10, pady=10)

    restock_code = tk.Entry(
        frame,
        font=("Arial", 12),
        width=20
    )

    restock_code.grid(
        row=0,
        column=1,
        padx=10,
        pady=10
    )

    tk.Label(
        frame,
        text="Quantity:",
        font=("Arial", 12)
    ).grid(row=1, column=0, padx=10, pady=10)

    restock_qty = tk.Entry(
        frame,
        font=("Arial", 12),
        width=20
    )

    restock_qty.grid(
        row=1,
        column=1,
        padx=10,
        pady=10
    )

    def restock():

        code = restock_code.get().strip().upper()

        try:
            quantity = int(restock_qty.get())

            if quantity <= 0:
                raise ValueError

        except ValueError:

            messagebox.showerror(
                "Error",
                "Enter a valid quantity."
            )
            return

        cursor.execute(
            "SELECT name FROM products WHERE code=?",
            (code,)
        )

        product = cursor.fetchone()

        if not product:

            messagebox.showerror(
                "Error",
                "Item code not found."
            )
            return

        cursor.execute("""
            UPDATE products
            SET stock = stock + ?
            WHERE code=?
        """, (quantity, code))

        conn.commit()

        messagebox.showinfo(
            "Success",
            f"{quantity} units added to {product[0]}."
        )

        restock_code.delete(0, tk.END)
        restock_qty.delete(0, tk.END)

        speak("Stock updated successfully")

    tk.Button(
        window,
        text="RESTOCK",
        font=("Arial", 12, "bold"),
        width=20,
        command=restock
    ).pack(pady=20)


# =========================================================
# ADD NEW PRODUCT
# =========================================================

def add_product_window():

    window = tk.Toplevel(root)

    window.title("Add New Product")
    window.geometry("500x550")

    tk.Label(
        window,
        text="ADD NEW PRODUCT",
        font=("Arial", 18, "bold")
    ).pack(pady=20)

    frame = tk.Frame(window)
    frame.pack(pady=10)

    labels = [
        "Item Code",
        "Item Name",
        "Price",
        "Stock",
        "GST %"
    ]

    entries = []

    for i, label in enumerate(labels):

        tk.Label(
            frame,
            text=label + ":",
            font=("Arial", 12)
        ).grid(
            row=i,
            column=0,
            padx=10,
            pady=10
        )

        entry = tk.Entry(
            frame,
            font=("Arial", 12),
            width=22
        )

        entry.grid(
            row=i,
            column=1,
            padx=10,
            pady=10
        )

        entries.append(entry)

    def save_product():

        code = entries[0].get().strip().upper()
        name = entries[1].get().strip()

        try:
            price = float(entries[2].get())
            stock = int(entries[3].get())
            gst = float(entries[4].get())

            if price < 0 or stock < 0 or gst < 0:
                raise ValueError

        except ValueError:

            messagebox.showerror(
                "Error",
                "Please enter valid product details."
            )
            return

        if not code or not name:

            messagebox.showerror(
                "Error",
                "Code and name are required."
            )
            return

        try:

            cursor.execute("""
                INSERT INTO products
                (code, name, price, stock, gst)
                VALUES (?, ?, ?, ?, ?)
            """, (
                code,
                name,
                price,
                stock,
                gst
            ))

            conn.commit()

            messagebox.showinfo(
                "Success",
                "Product added successfully."
            )

            for entry in entries:
                entry.delete(0, tk.END)

            speak("New product added")

        except sqlite3.IntegrityError:

            messagebox.showerror(
                "Error",
                "This item code already exists."
            )

    tk.Button(
        window,
        text="SAVE PRODUCT",
        font=("Arial", 12, "bold"),
        width=20,
        command=save_product
    ).pack(pady=20)


# =========================================================
# BILLING TAB
# =========================================================

billing_frame = tk.Frame(root)

billing_frame.pack(
    fill="both",
    expand=True
)

# =========================================================
# TITLE
# =========================================================

title = tk.Label(
    billing_frame,
    text="SUPERMARKET BILLING SYSTEM",
    font=("Arial", 24, "bold")
)

title.pack(pady=15)


# =========================================================
# INVOICE
# =========================================================

invoice_frame = tk.Frame(billing_frame)

invoice_frame.pack(
    fill="x",
    padx=20
)

tk.Label(
    invoice_frame,
    text="Invoice No:",
    font=("Arial", 12, "bold")
).pack(side="left")

tk.Label(
    invoice_frame,
    textvariable=invoice_var,
    font=("Arial", 12, "bold")
).pack(side="left", padx=10)


# =========================================================
# ITEM INPUT
# =========================================================

input_frame = tk.LabelFrame(
    billing_frame,
    text="Add Item",
    font=("Arial", 12, "bold")
)

input_frame.pack(
    fill="x",
    padx=20,
    pady=10
)


tk.Label(
    input_frame,
    text="Item Code:"
).grid(
    row=0,
    column=0,
    padx=10,
    pady=10
)

code_entry = tk.Entry(
    input_frame,
    textvariable=code_var,
    font=("Arial", 12),
    width=15
)

code_entry.grid(
    row=0,
    column=1,
    padx=10,
    pady=10
)

code_entry.bind(
    "<Return>",
    search_product
)


tk.Label(
    input_frame,
    text="Quantity:"
).grid(
    row=0,
    column=2,
    padx=10,
    pady=10
)

quantity_entry = tk.Entry(
    input_frame,
    textvariable=quantity_var,
    font=("Arial", 12),
    width=10
)

quantity_entry.grid(
    row=0,
    column=3,
    padx=10,
    pady=10
)


tk.Label(
    input_frame,
    text="Item:"
).grid(
    row=1,
    column=0,
    padx=10,
    pady=10
)

tk.Label(
    input_frame,
    textvariable=item_name_var,
    font=("Arial", 11, "bold")
).grid(
    row=1,
    column=1,
    padx=10,
    pady=10
)


tk.Label(
    input_frame,
    text="Price:"
).grid(
    row=1,
    column=2,
    padx=10,
    pady=10
)

tk.Label(
    input_frame,
    textvariable=price_var
).grid(
    row=1,
    column=3,
    padx=10,
    pady=10
)


tk.Label(
    input_frame,
    text="GST:"
).grid(
    row=2,
    column=0,
    padx=10,
    pady=10
)

tk.Label(
    input_frame,
    textvariable=gst_var
).grid(
    row=2,
    column=1,
    padx=10,
    pady=10
)


tk.Label(
    input_frame,
    text="Available Stock:"
).grid(
    row=2,
    column=2,
    padx=10,
    pady=10
)

tk.Label(
    input_frame,
    textvariable=stock_var
).grid(
    row=2,
    column=3,
    padx=10,
    pady=10
)


tk.Button(
    input_frame,
    text="SEARCH",
    width=12,
    command=search_product
).grid(
    row=0,
    column=4,
    padx=10
)


tk.Button(
    input_frame,
    text="ADD ITEM",
    width=12,
    command=add_item
).grid(
    row=1,
    column=4,
    padx=10
)


# =========================================================
# BILL TABLE
# =========================================================

table_frame = tk.Frame(billing_frame)

table_frame.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=10
)

columns = (
    "code",
    "name",
    "qty",
    "price",
    "gst",
    "gst_amount",
    "total"
)

bill_tree = ttk.Treeview(
    table_frame,
    columns=columns,
    show="headings",
    height=10
)

bill_tree.heading("code", text="Code")
bill_tree.heading("name", text="Item")
bill_tree.heading("qty", text="Qty")
bill_tree.heading("price", text="Price")
bill_tree.heading("gst", text="GST")
bill_tree.heading("gst_amount", text="GST Amount")
bill_tree.heading("total", text="Total")

bill_tree.column("code", width=70)
bill_tree.column("name", width=180)
bill_tree.column("qty", width=60)
bill_tree.column("price", width=90)
bill_tree.column("gst", width=80)
bill_tree.column("gst_amount", width=100)
bill_tree.column("total", width=100)

bill_tree.pack(
    fill="both",
    expand=True
)


# =========================================================
# TOTAL FRAME
# =========================================================

total_frame = tk.Frame(billing_frame)

total_frame.pack(
    fill="x",
    padx=30,
    pady=5
)

tk.Label(
    total_frame,
    text="Subtotal:",
    font=("Arial", 12, "bold")
).grid(
    row=0,
    column=0,
    padx=20
)

tk.Label(
    total_frame,
    textvariable=subtotal_var,
    font=("Arial", 12)
).grid(
    row=0,
    column=1
)


tk.Label(
    total_frame,
    text="GST:",
    font=("Arial", 12, "bold")
).grid(
    row=0,
    column=2,
    padx=20
)

tk.Label(
    total_frame,
    textvariable=gst_total_var,
    font=("Arial", 12)
).grid(
    row=0,
    column=3
)


tk.Label(
    total_frame,
    text="Grand Total:",
    font=("Arial", 14, "bold")
).grid(
    row=0,
    column=4,
    padx=20
)

tk.Label(
    total_frame,
    textvariable=grand_total_var,
    font=("Arial", 14, "bold")
).grid(
    row=0,
    column=5
)


# =========================================================
# BUTTON FRAME
# =========================================================

button_frame = tk.Frame(billing_frame)

button_frame.pack(
    pady=15
)


tk.Button(
    button_frame,
    text="REMOVE ITEM",
    width=15,
    command=remove_item
).grid(
    row=0,
    column=0,
    padx=5
)


tk.Button(
    button_frame,
    text="GENERATE BILL",
    width=18,
    command=generate_bill
).grid(
    row=0,
    column=1,
    padx=5
)


tk.Button(
    button_frame,
    text="STOCK",
    width=15,
    command=stock_window
).grid(
    row=0,
    column=2,
    padx=5
)


tk.Button(
    button_frame,
    text="RESTOCK",
    width=15,
    command=restock_window
).grid(
    row=0,
    column=3,
    padx=5
)


tk.Button(
    button_frame,
    text="ADD PRODUCT",
    width=15,
    command=add_product_window
).grid(
    row=0,
    column=4,
    padx=5
)


tk.Button(
    button_frame,
    text="CLEAR",
    width=15,
    command=lambda: [
        cart.clear(),
        refresh_cart(),
        calculate_total(),
        clear_item_fields()
    ]
).grid(
    row=0,
    column=5,
    padx=5
)


# =========================================================
# START
# =========================================================

update_invoice_display()
calculate_total()

root.mainloop()
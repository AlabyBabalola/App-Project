import sqlite3
import bcrypt
import random
import os
from datetime import datetime, timedelta

DB_NAME = "ramzone_enterprise.db"
LOW_STOCK_THRESHOLD = 10

# =====================================================
# DATABASE
# =====================================================

def get_db():
    return sqlite3.connect(DB_NAME)
def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password BLOB,
        role TEXT,
        is_verified INTEGER DEFAULT 0,
        failed_attempts INTEGER DEFAULT 0,
        locked_until TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS login_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        login_time TEXT,
        status TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        price REAL,
        purchase_price REAL,
        stock INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT,
        quantity INTEGER,
        total_price REAL,
        seller TEXT,
        sale_date TEXT
    )
    """)

    conn.commit()
    conn.close()

# =====================================================
# UTILITIES
# =====================================================

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def log_login(email, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO login_history(email,login_time,status) VALUES(?,?,?)",
                   (email, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status))
    conn.commit()
    conn.close()

# def auto_backup():
#     if not os.path.exists("backups"):
#         os.makedirs("backups")
#     shutil.copy(DB_NAME, f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

# =====================================================
# EMAIL SYSTEM
# =====================================================

# def send_approval_email(to_email):
#     sender = "tonemail@gmail.com"
#     password = "mot_de_passe_application"

#     message = MIMEText("Votre compte a été approuvé. Vous pouvez maintenant vous connecter.")
#     message["Subject"] = "Compte approuvé - RAMZONE"
#     message["From"] = sender
#     message["To"] = to_email

#     try:
#         server = smtplib.SMTP("smtp.gmail.com", 587)
#         server.starttls()
#         server.login(sender, password)
#         server.sendmail(sender, to_email, message.as_string())
#         server.quit()
#         print("Email envoyé ✅")
#     except Exception as e:
#         print("Erreur email:", e)

# =====================================================
# AUTHENTICATION
# =====================================================

def register():
    conn = get_db()
    cursor = conn.cursor()

    try:
        email = input("Email: ")
        password = input("Password: ")

        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        # 👑 Premier inscrit = Admin automatiquement validé
        if user_count == 0:
            role = "admin"
            is_verified = 1
            print("Premier compte créé : ADMIN validé automatiquement ✅")
        else:
            role = "user"
            is_verified = 0
            print("Compte créé ✅ En attente d'approbation.")

        try:
            cursor.execute(
                "INSERT INTO users(email,password,role,is_verified) VALUES(?,?,?,?)",
                (email, hash_password(password), role, is_verified)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            print("Email déjà utilisé ❌")
        except Exception as e:
            print(f"Erreur inattendue : {e}")
    finally:
        conn.close()

def edit_product():
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Afficher tous les produits
        cursor.execute("SELECT id, name, price, purchase_price, stock FROM products")
        products = cursor.fetchall()
        for p in products:
            print(f"{p[0]} | {p[1]} | {p[2]}€ | {p[3]}€ | {p[4]} unités")

        # 2. Demander l'ID
        product_id = input("ID du produit à modifier: ")

        # 3. Demander les nouvelles valeurs
        name = input("Nouveau nom: ")
        purchase = float(input("Prix achat: "))
        sale = float(input("Prix vente: "))
        stock = int(input("Stock: "))

        # 4. Mettre à jour
        cursor.execute("UPDATE products SET name=?, price=?, purchase_price=?, stock=? WHERE id=?",
                (name, sale, purchase, stock, product_id))
        conn.commit()
        print("Produit modifié ✅")
    except ValueError:
        print("Valeur incorrecte ❌")
    except Exception as e:
        print(f"Erreur inattendue : {e}")
    finally:
        conn.close()

def login():
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        email = input("Email: ")

        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        
        if not user:
            print("Email incorrect ❌")
            return None
    

        # Vérification approbation
        if user[4] == 0:
            print("Compte en attente d'approbation ⏳")
            return None
        
#       ===== Verifier si bloque ===
        locked_until = user[6]
        if locked_until:
            locked_time = datetime.strptime(locked_until,"%Y-%m-%d %H:%M:%S")
            if datetime.now() < locked_time:
                remaining = (locked_time - datetime.now()).seconds// 60
                print(f"Compte bloque ⛔ Reesayez dans {remaining} minutes")
                return None
            

        # Vérification mot de passe
        for failed_attemps in range(3):
            password = input("Mot de passe: ")
            if check_password(password, user[2]):
                break
            else:
                print(f"Mot de passe incorrect ❌ {failed_attemps+1}/3")
                log_login(email, "FAILED")
        else:
            print("Trop de tentative")
            cursor.execute("UPDATE users SET locked_until=? WHERE email=?",((datetime.now() + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"), email))
            conn.commit()
            print("Compte bloqué 1 minutes ⛔")
            return None
        

        # ================= 2FA =================
        code = str(random.randint(100000, 999999))
        print(f"[CODE 2FA]: {code}")

        user_code = input("Entrer le code 2FA: ")

        if user_code != code:
            print("Code 2FA incorrect ❌")
            log_login(email, "FAILED_2FA")
            return None

        log_login(email, "SUCCESS")
        print("Connexion réussie ✅")
        return user
    finally:
        conn.close()


def delete_product():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name FROM products")    
        products = cursor.fetchall()
        for p in products:
            print(f"{p[0]} | {p[1]}") 
        product_id = input("ID du produit à modifier: ")
        cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
        print(f"Produit {product_id} supprime ")
        conn.commit()
    finally:
        conn.close()

# =====================================================
# ADMIN USER MANAGEMENT
# =====================================================

def approve_user():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id,email,role FROM users WHERE is_verified=0")
        users = cursor.fetchall()

        if not users:
            print("Aucun utilisateur en attente.")
            return

        print("\n=== UTILISATEURS EN ATTENTE ===")
        print("ID | EMAIL | ROLE")
        print("----------------------------")

        for u in users:
            print(f"{u[0]} | {u[1]} | {u[2]}")

        ids = input("\nEntrer les IDs à approuver (ex: 2,3,5) : ")

        id_list = ids.split(",")

        for user_id in id_list:
            user_id = user_id.strip()
            cursor.execute("UPDATE users SET is_verified=1 WHERE id=?", (user_id,))

        conn.commit()
        

        print("Utilisateur(s) approuvé(s) ✅")
    finally:
        conn.close()

def view_stock_user():
    conn = get_db()
    cursor = conn.cursor()
    try: 
        cursor.execute("SELECT name, stock FROM products")
        products = cursor.fetchall()

        print("\n===== STOCK DISPONIBLE =====")
        print("Produit | Quantité")
        print("----------------------")

        for p in products:
            print(f"{p[0]} | {p[1]} unités")
    finally:
        conn.close()

def reject_user():
    conn = get_db()
    cursor = conn.cursor()  
    try:
        cursor.execute("SELECT id,email FROM users WHERE is_verified=0")
        users = cursor.fetchall()

        for u in users:
            print(f"{u[0]} - {u[1]}")

        user_id = input("ID à refuser: ")

        cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
        

        print("Utilisateur refusé ❌")
    finally:
        conn.close()

def delete_user():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id,email,role FROM users")
        users = cursor.fetchall()

        for u in users:
            print(f"{u[0]} - {u[1]} ({u[2]})")

        user_id = input("ID à supprimer: ")

        cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()

        print("Utilisateur supprimé 🗑")
    finally:
        conn.close()

def change_role():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id,email,role FROM users")
        users = cursor.fetchall()

        for u in users:
            print(f"{u[0]} - {u[1]} ({u[2]})")

        user_id = input("ID utilisateur: ")
        new_role = input("Nouveau rôle (admin/user): ")

        if new_role not in ["admin", "user"]:
            print("Rôle invalide ❌")
            return

        cursor.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
        conn.commit()

        print("Rôle mis à jour 🔄")
    finally:
        conn.close()

# =====================================================
# PRODUCTS & SALES
# =====================================================

def add_product():
    conn = get_db()
    cursor = conn.cursor()

    try:
        name = input("Nom produit: ")
        try:
            purchase = float(input("Prix achat: "))
            sale = float(input("Prix vente: "))
            stock = int(input("Stock: "))
        except ValueError:
            print("Valeur incorrect, veuillez entrez un nombre.")
            return

        cursor.execute("INSERT INTO products(name,price,purchase_price,stock) VALUES(?,?,?,?)",
                    (name, sale, purchase, stock))
        conn.commit()
    finally:
        conn.close()

def register_sale(user):
    conn = get_db()
    cursor = conn.cursor()

    try:
        name = input("Produit: ")
        try:
            qty = int(input("Quantité: "))
        except ValueError:
            print("Valeur incorrect, veuillez entrez un nombre.")
            return

        cursor.execute("SELECT price,stock FROM products WHERE name=?", (name,))
        p = cursor.fetchone()

        if not p or p[1] < qty:
            print("Stock insuffisant ❌")
            return


        total = p[0] * qty

        cursor.execute("UPDATE products SET stock=stock-? WHERE name=?", (qty, name))
        cursor.execute("INSERT INTO sales(product_name,quantity,total_price,seller,sale_date) VALUES(?,?,?,?,?)",
                    (name, qty, total, user[1], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

        conn.commit()
        print("Vente enregistrée ✅")
    finally:
        conn.close()
    # auto_backup()

# =====================================================
# REPORTS
# =====================================================

def daily_report():
    conn = get_db()
    cursor = conn.cursor()
    try:
        today = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("SELECT product_name,quantity FROM sales WHERE sale_date LIKE ?",
                    (today + "%",))
        rows = cursor.fetchall()
        print("\n===== JOURNAL JOURNALIER =====")
        for r in rows:
            print(f"{r[0]} | {r[1]} unités")

        cursor.execute("SELECT SUM(total_price) FROM sales WHERE sale_date LIKE ?", (today + "%",))
        total = cursor.fetchone()[0] or 0
        print(f"\nTotal du jour : {total} $")
    finally:
        conn.close()


def monthly_report():
    conn = get_db()
    cursor = conn.cursor()
    try:
        month = datetime.now().strftime("%Y-%m")

        cursor.execute("SELECT product_name,SUM(quantity) FROM sales WHERE sale_date LIKE ? GROUP BY product_name",
                    (month + "%",))
        rows = cursor.fetchall()

        print("\n===== JOURNAL MENSUEL =====")
        for r in rows:
            print(f"{r[0]} | {r[1]} unités")
    finally:
        conn.close()

def monthly_comparison():
    conn = get_db()
    cursor = conn.cursor()

    try:
        now = datetime.now()
        current = now.strftime("%Y-%m")
        prev = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

        cursor.execute("SELECT SUM(quantity) FROM sales WHERE sale_date LIKE ?", (current + "%",))
        c_qty = cursor.fetchone()[0] or 0

        cursor.execute("SELECT SUM(quantity) FROM sales WHERE sale_date LIKE ?", (prev + "%",))
        p_qty = cursor.fetchone()[0] or 0

        print("\n===== COMPARAISON MENSUELLE =====")
        print(f"{current}: {c_qty} unités")
        print(f"{prev}: {p_qty} unités")
    finally:
        conn.close()

def top_seller():
    conn = get_db()
    cursor = conn.cursor()
    month = datetime.now().strftime("%Y-%m")
    try:
        cursor.execute("""
            SELECT seller,SUM(quantity)
            FROM sales
            WHERE sale_date LIKE ?
            GROUP BY seller
            ORDER BY SUM(quantity) DESC
            LIMIT 1
        """, (month + "%",))

        result = cursor.fetchone()

        print("\n===== TOP VENDEUR =====")
        if result:
            print(f"{result[0]} | {result[1]} unités")
        else:
            print("Aucune vente.")
    finally:
        conn.close()

def stock_alert():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name,stock FROM products WHERE stock<=?",
                    (LOW_STOCK_THRESHOLD,))
        rows = cursor.fetchall()

        print("\n===== ALERTE STOCK =====")
        for r in rows:
            print(f"{r[0]} | {r[1]} unités")
    finally:
        conn.close()


def view_stock_admin():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name, stock, price, purchase_price FROM products")
        products = cursor.fetchall()

        print("\n===== STOCK COMPLET (ADMIN) =====")
        print("Produit | Stock | Prix Vente | Prix Achat")
        print("--------------------------------------------------")

        for p in products:
            print(f"{p[0]} | {p[1]} unités | {p[2]} € | {p[3]} €")
    finally:
        conn.close()

def view_login_history():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email, login_time, status FROM login_history")
        history = cursor.fetchall()

        print("\n=== HISTORIQUE CONNEXIONS ====")
        for h in history:
            print(f"{h[0]} | {h[1]} | {h[2]}")
    finally:
        conn.close()

# =====================================================
# MENU
# =====================================================

def main_menu(user):
    role = user[3]

    try:
        while True:

            # ================= ADMIN =================
            if role == "admin":
                print("""
=========== MENU ADMIN ===========
1 Ajouter produit
2 Enregistrer vente
3 Voir stock complet
4 Journal journalier
5 Journal mensuel
6 Comparaison mensuelle
7 Top vendeur
8 Alerte stock
9 Approuver utilisateur
10 Refuser utilisateur
11 Supprimer utilisateur
12 Changer rôle
13 Modifier produit
14 Supprimer produit
15 Login History
0 Déconnexion
""")

                c = input("Choix: ")

                if c == "1":
                    add_product()
                elif c == "2":
                    register_sale(user)
                elif c == "3":
                    view_stock_admin()
                elif c == "4":
                    daily_report()
                elif c == "5":
                    monthly_report()
                elif c == "6":
                    monthly_comparison()
                elif c == "7":
                    top_seller()
                elif c == "8":
                    stock_alert()
                elif c == "9":
                    approve_user()
                elif c == "10":
                    reject_user()
                elif c == "11":
                    delete_user()
                elif c == "12":
                    change_role()
                elif c == "13":
                    edit_product()
                elif c == "14":
                    delete_product()
                elif c == "15":
                    view_login_history()
                elif c == "0":
                    print("Déconnexion 👋")
                    break
                else:
                    print("Choix invalide ❌")

            # ================= USER =================
            else:
                print("""
=========== MENU USER ===========
1 Ajouter produit
2 Enregistrer vente
3 Voir stock
4 Journal journalier
5 Journal mensuel
0 Déconnexion
""")

                c = input("Choix: ")

                if c == "1":
                    add_product()
                elif c == "2":
                    register_sale(user)
                elif c == "3":
                    view_stock_user()
                elif c == "4":
                    daily_report()
                elif c == "5":
                    monthly_report()
                elif c == "0":
                    print("Déconnexion 👋")
                    break
                else:
                    print("Choix invalide ❌")

    except KeyboardInterrupt:
        print("\nRetour au menu principal 👋")

# =====================================================
# START
# =====================================================

init_db()

try:
    while True:
        print("""
===== RAMZONE ENTERPRISE =====
1 Inscription
2 Connexion
0 Quitter
""")

        choice = input("Choix: ")

        if choice == "1":
            register()
        elif choice == "2":
            user = login()
            if user:
                main_menu(user)
        elif choice == "0":
            print("Au revoir 👋")
            break
        else:
            print("Choix invalide ❌")

except KeyboardInterrupt:
    print("\n\nProgramme arrêté proprement 👋")
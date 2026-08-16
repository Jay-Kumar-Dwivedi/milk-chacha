import mysql.connector

def get_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Golgappu@0882",      # अगर password है तो यहाँ लिखो
        database="milk_chacha"
    )
    return connection
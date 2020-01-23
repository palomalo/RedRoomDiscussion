import sqlite3

conn = sqlite3.connect('user.db')
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS user (
            userName password,
            password password
            )""")

class UserDB:

    def insert_User(self, userName, password):
        with conn:
            c.execute("INSERT INTO user VALUES (:userName, :password)", {'userName': userName, 'password': password})

    def get_user_by_name(self, userName):
        c.execute("SELECT * FROM user WHERE userName=:userName", {'userName': userName})
        return c.fetchall()

    def getAlluser(self):
        c.execute("SELECT * FROM user")
        return c.fetchall()

    def update_UserName(self, userName, password):
        with conn:
            c.execute("""UPDATE user SET userName = :userName
                        WHERE password = :password """,
                      {'userName': userName, 'password': password})

    def remove_User(self, userName, password):
        with conn:
            c.execute("DELETE from user WHERE userName = :userName AND password = :password",
                      {'userName': userName, 'password': password})

#  top1 = user('topic1', 'bsppassword')
# top2 = user('topic2', 'bsppassword2')

# insert_topic(top1)
# insert_topic(top2)

# allTops = DbgetAlluser()

# user = get_user_by_name('topic1')
#  print(user)

# update_password(top2, "newTopic")
# remove_emp(top1)

# tops = get_user_by_name('topic2')
# print(tops)
# print(allTops)

import sqlite3


# conn = sqlite3.connect('topics_new1.db')
# c = conn.cursor()
from itertools import chain


class Topics:

    def getConnection(self):
        def dict_factory(cursor, row):
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d
        conn = sqlite3.connect('topics_new1.db')
        conn.row_factory = dict_factory
        return conn

    def getCursor(self, conn):
        return conn.cursor

    def insert_topic(self, topicName, text):
        with self.getConnection:
            self.getCursor(self.getConnection()).execute("INSERT INTO topics_new1 VALUES (:topicName, :text)",
                                                         {'topicName': topicName, 'text': text})



    # def get_topics_new1_by_name(self, topicName):
    #   c.execute("SELECT * FROM topics_new1 WHERE topicName=:topicName", {'topicName': topicName})
    #  print(c.fetchall())
    # return c.fetchall()

    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def getAllTopics(self):
        def dict_factory(cursor, row):
            d = {}
            for idx, col in enumerate(cursor.description):
                d[col[0]] = row[idx]
            return d
        connection = sqlite3.connect("topics_new1.db")
        connection.row_factory = dict_factory
        cursor = connection.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS topics_new1 (
                    topicName text,
                    text text
                    )""")
        cursor.execute("select * from topics_new1")

        #first_row = next(cursor.fetchone())
        #for row in chain((first_row,), cursor.fetchone()):
        return cursor.fetchall()
        #return "empty table topics"



# def update_text(emp, text):
#  with conn:
#  c.execute("""UPDATE topics_new1 SET text = :text
#      WHERE topicName = :topicName """,
#    {'topicName': emp.topicName, 'text': emp.text})

# def remove_emp(self, topicName, text):
# with conn:
#   c.execute("DELETE from topics_new1 WHERE topicName = :topicName AND text = :text",
#  {'topicName': topicName, 'text': text})


# my_query = query_db("select * from majorroadstiger limit %s", (3,))

#  top1 = topics_new1('topic1', 'bspTExt')
# top2 = topics_new1('topic2', 'bsptext2')

# insert_topic(top1)
# insert_topic(top2)

# topics_new1 = get_topics_new1_by_name('topic1')
#  print(topics_new1)

# update_text(top2, "newTopic")
# remove_emp(top1)

# tops = get_topics_new1_by_name('topic2')
# print(tops)
# print(allTops)

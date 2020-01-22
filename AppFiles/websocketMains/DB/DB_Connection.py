import sqlite3
from AppFiles.websocketMains.DB.Topics import Topics

conn = sqlite3.connect('topics.db')
c = conn.cursor()

c.execute("""CREATE TABLE IF NOT EXISTS topics (
            topicName text,
            text text
            )""")


class DB_Connection:

    def insert_topic(self, topicName, text):
        with conn:
            c.execute("INSERT INTO topics VALUES (:topicName, :text)", {'topicName': topicName, 'text': text})

    def get_topics_by_name(self, topicName):
        c.execute("SELECT * FROM topics WHERE topicName=:topicName", {'topicName': topicName})
        return c.fetchall()

    def getAllTopics(self):
        c.execute("SELECT * FROM topics")
        return c.fetchall()

    def update_text(emp, text):
        with conn:
            c.execute("""UPDATE topics SET text = :text
                        WHERE topicName = :topicName """,
                      {'topicName': emp.topicName, 'text': emp.text})

    def remove_emp(self, topicName,text):
        with conn:
            c.execute("DELETE from topics WHERE topicName = :topicName AND text = :text",
                      {'topicName': topicName, 'text': text})

#  top1 = Topics('topic1', 'bspTExt')
# top2 = Topics('topic2', 'bsptext2')

# insert_topic(top1)
# insert_topic(top2)

# allTops = DbgetAllTopics()

# topics = get_topics_by_name('topic1')
#  print(topics)

# update_text(top2, "newTopic")
# remove_emp(top1)

# tops = get_topics_by_name('topic2')
# print(tops)
# print(allTops)

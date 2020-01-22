
class Topics:
    """A sample Employee class"""

    def __init__(self, topicName, text):
        self.topicName = topicName
        self.text = text

    @property
    def getTopicName(self):
        return '{}'.format(self.topicName)

    @property
    def getTextName(self):
        return '{}'.format(self.text)

    def __repr__(self):
        return "Topic('{}', '{}')".format(self.topicName, self.text)

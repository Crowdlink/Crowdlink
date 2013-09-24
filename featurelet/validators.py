
class UnicodeStringValidator(object):
    """

    :param message: (optional) The message to present to the user upon failure.
    :type message: string
    """

    def __init__(self,
                 spmsg=None,
                 minmsg=None,
                 maxmsg=None,
                 minval=3,
                 maxval=28):
        self.minval = minval
        self.maxval = maxval
        self.spmsg = spmsg if spmsg else "Usernames cannot contain spaces"
        self.minmsg = minmsg if minmsg else "Minimum of {0} characters".format(minval)
        self.maxmsg = maxmsg if maxmsg else "No more than {0} characters".format(maxval)

    def __call__(self, username):
        if ' ' in username.data:
            username.add_error({'message': self.spmsg})
        if len(username.data) < self.minval:
            username.add_error({'message': self.minmsg})
        if len(username.data) > self.maxval:
            username.add_error({'message': self.maxmsg})

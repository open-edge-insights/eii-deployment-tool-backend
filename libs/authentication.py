# Copyright (c) 2021 Intel Corporation.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

""" Module for handling authentication """

import secrets
from fastapi import HTTPException, Depends
from fastapi import status as HTTPStatus
from fastapi.security import APIKeyCookie

class Authentication():
    """ Class for grouping authentication related functions and data """
    tokens = {}
    SESSION_NAME = "dt_session"
    session_cookie = APIKeyCookie(name=SESSION_NAME)
    def __init__(self):
        pass

    def generate_token(self, username):
        """Generates and returns a secure token and associates the specified
           user with the same

        :param username: Username
        :type username: str
        :return: toke
        "rtype: str
        """
        _ = self
        token = secrets.token_urlsafe(16)
        Authentication.tokens[token] = username
        return token


    @staticmethod
    def get_user_credentials(username, creds):
        """Returns the login credentials for the give username

        :param username: Username
        :type username: str
        :return: user login credentails
        "rtype: ()
        """
        if username in creds:
            return creds[username]
        return None

    @staticmethod
    def validate_session(token: str = Depends(session_cookie)):
        """Checks whether the given token is valid

        :param token: session token returned by /eii/ui/login API
        :type token: str
        :return: Whether token is valid or not
        :rtype: bool
        """
        if token not in Authentication.tokens:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN,
                detail="Invalid authentication"
            )
        return token

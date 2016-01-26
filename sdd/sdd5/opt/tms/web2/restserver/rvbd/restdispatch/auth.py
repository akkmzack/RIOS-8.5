
class AuthModule:

    def __init__(self, engine):
        self.__engine = engine

    def get_engine(self):
        """!
        Returns a reference to the engine.
        @return reference to the engine.
        """
        return self.__engine
    
    def get_access_code(self, jti):
        """!
        Get the access code for the given jti.
        Return the access code stored inside the product specific database.
        None if not a valid code.
        @param jti the jti.
        @return the access code.
        """

        self.get_engine().log_error('get_access_code not implemented')
        return None

    def get_access_token(self, jti):
        """!
        Get the access token for the given jti.
        Return the access token stored inside the product specific database.
        None if not a valid token.
        @param jti the jti.
        @return the access token.
        """

        self.get_engine().log_error('get_access_token not implemented')
        return None

    def store_access_token(self, code_claims, token_claims, token):
        """!
        Store the given access token.
        The code_claims and token_claims are provided as additional
        meta data. The token parameter is the one that needs to be
        stored.
        @param code_claims claims object representing the access code.
        @param token_claims claims object representing the access token.
        @param token the token to store.
        @return True if successful or False if unsuccessful.
        """

        self.get_engine().log_error('store_access_token not implemented')
        return False

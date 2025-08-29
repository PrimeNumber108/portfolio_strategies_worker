

# API Credentials


params = {
    "API_KEY":"",
    "SECRET_KEY":"",
    "PASSPHRASE":"",
    # Exchange Configuration
    "EXCHANGE" :"",
    "PAPER_MODE" :  False,
    "SESSION_ID":"",
    "STRATEGY_NAME":"",
}

def set_constants(args):
    global params
    params["SESSION_ID"] = args[1]
    params["EXCHANGE"] = args[2]
    params["API_KEY"] = args[3]
    params["SECRET_KEY"] = args[4]
    params["PASSPHRASE"] = args[5]
    params["STRATEGY_NAME"] = args[6]
    params["PAPER_MODE"] = True if args[7].lower() == 'true' else False

    
  

def get_constants():
    global params
    return params
  

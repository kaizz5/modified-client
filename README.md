# modified-client

Basically, the code 4transactions.py is just a modification of client.py. I used this code for performance comparison of protocol modes (load-balancing and non-load-balancing)
This program runs 4 transactions. The first transaction is in load balancing mode and the other 3 transactions are in non-load-balancing mode. After performing the 4 transactions,
it will print to the console the result details of each transaction.

Environment setup: You can only run this code in unix-based os because the code contains methods that are only available on linux os or unix-based systems.

 The format of command to run the code:
    python3 4transactions.py -a <orchestrator's IP address> -p <Orchestrator's port number> -f <filename> -m <1/2> -s <1/2/3>
    
To make a successful run of this code, make sure that the orchestrator will not perform consecutive testing (same IP address). 
To pull this off, I used another local machine to send request/intent message (alternate request from local machine and AWS).



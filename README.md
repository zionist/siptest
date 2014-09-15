====== Simple SIP load test tool with RTP and statistic =====

Requirements:
    python == 2.7
    python-dev

Installation:
    git clone git@git.teligent.ru:stanislav.krizhanovsky/loadtest.git
    cd loadtest/siptest
    python setup.py install

Purposes:
    Simple SIP load test tool. Generate simple statistic for each call leg. 

Notes:
   Runs separate proccess for each call leg

Run:
    siptest -f list_of_users -r |runs| -d |call_duration_in_seconds|

Help:
    siptest -h

Example run:
    siptest -f list_of_users100 -r files/g711a.pcap

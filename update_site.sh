#!/bin/bash
python3 manage.py migrate && \
python3 manage.py check &&
sudo bash make_style.sh && \
python3 manage.py collectstatic --noinput && \
python3 manage.py compilemessages && \
python3 manage.py compilejsi18n

printf "Do you use supervisor to run the site? [y\\\n]\n"
read useSuper
if [ $useSuper == "y" ]; then 
    printf "What is the name of the site process?\n"
    read siteProcessName
    sudo supervisorctl restart $siteProcessName
    echo "Restarted site process, please consider to restart the bridged + celery if needed"
fi

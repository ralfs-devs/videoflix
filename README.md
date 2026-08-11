# Videoflix

### A backend Application to provide an API for a  Platform to 
### organize Videofilms in different Qualities (480p, 720p and 1080p)

This project is in the early testing phase.  
**Disclaimer:** We assume no liability for damages of any kind.

You need to run a Docker environment, because the Application is organized
in docker several Docker containers.

## Installation in Your Local VSCode Environment:

Clone the repository:
~~~bash
git clone https://github.com/ralfs-devs/videoflix
~~~

### For installing and testing the API:
Navigate into the project folder:
~~~bash
cd ./videoflix
~~~

Create a virtual environment:
~~~bash
python -m venv .venv
~~~
(You may need to use python3 instead of python)

Activate the virtual environment:
##### Windows:
~~~bash
source .venv\Scripts\activate
~~~
##### macOS/Linux:
~~~bash
source .venv/bin/activate
~~~

look for actually installed Dependencies:
~~~bash
pip freeze
~~~

Install required packages:
~~~bash
pip install -r requirements.txt
~~~

Check whether all the necessary dependencies are installed:
~~~bash
pip freeze
~~~

copy the env.template to a .env file:
~~~bash
cp env_template .env
~~~

(Open this .env file in an editor
to change the SECRET_KEY to your personal setting)
and to determine your personal settings 
(eg. E-Mail settings and admin credentials)
caution: change only the values to your personal settings,
don't change any keyname

First start of the Docker Services:
~~~bash
docker compose up --build
~~~

to upload and convert videos to the Database please use the admin Endpoint:
127.0.0.1/admin/videos_app/video/

Thanks go to Developer Akademie GmbH for providing a 
Frontend Application for testing purposes:
https://github.com/Developer-Akademie-Backendkurs/project.Videoflix

## Testing Notes:

The global rate limit is currently disabled ("no limits").

To adjust rate limiting, modify the DEFAULT_THROTTLE_RATES value 
in settings.py with your preferred settings.

.PHONY: build clean serve deploy deploy-staging

build:
	python3 build.py

clean:
	rm -rf dist/ .cache/

serve:
	python3 -m http.server 8000 -d dist/

deploy:
	rsync -avz dist/ user@server:/var/www/site/

deploy-staging:
	rsync -avz dist/ staging:/var/www/site-staging/

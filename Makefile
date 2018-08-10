run-docker: 
	# Clear out cached docker-compose images
	yes | docker-compose rm -v
	# Rebuild and bring up services
	docker-compose up --build

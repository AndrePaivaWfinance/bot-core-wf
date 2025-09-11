.PHONY: run test docker clean

run:
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest -v

docker:
	docker build -t bot-framework .
	docker run -p 8000:8000 bot-framework

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
	rm -rf .cache
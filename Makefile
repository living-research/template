.PHONY: run clean

run:
	@echo "Running notebooks..."
	@for nb in notebooks/*.ipynb; do \
		[ -f "$$nb" ] || continue; \
		echo "→ $$nb"; \
		jupyter nbconvert --to notebook --execute "$$nb" \
			--ExecutePreprocessor.timeout=600 \
			--output /dev/null; \
	done

clean:
	rm -rf data/processed/* results/*

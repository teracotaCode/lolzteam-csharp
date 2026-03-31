.PHONY: generate build test clean pack

SCHEMA_DIR := schemas
GEN_DIR := src/Lolzteam/Generated

generate:
	python3 codegen/generate.py --schema $(SCHEMA_DIR)/forum.json --output-dir $(GEN_DIR)/Forum --namespace Lolzteam.Generated.Forum
	python3 codegen/generate.py --schema $(SCHEMA_DIR)/market.json --output-dir $(GEN_DIR)/Market --namespace Lolzteam.Generated.Market

build:
	dotnet build Lolzteam.sln -c Release

test:
	dotnet test Lolzteam.sln -c Release --verbosity normal

clean:
	dotnet clean Lolzteam.sln
	rm -rf src/Lolzteam/Generated/Forum/Models/*.cs
	rm -rf src/Lolzteam/Generated/Forum/Enums/*.cs
	rm -rf src/Lolzteam/Generated/Market/Models/*.cs
	rm -rf src/Lolzteam/Generated/Market/Enums/*.cs

pack:
	dotnet pack src/Lolzteam/Lolzteam.csproj -c Release -o publish/

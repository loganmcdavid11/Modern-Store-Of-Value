# Modern-Store-Of-Value
Advanced Data Science Project 

To see research and results, view `research_poster` and `modern_store_of_value_presentaion`.

 
## Getting Started
 
### Prerequisites
You may need to install `uv` on your local machine before proceeding. See the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) for instructions.
 
### Setup
In the VSCode terminal, run the following to automatically install all project dependencies:
 
```bash
uv sync
```
 
---
 
## Notebooks
 
Each team member should create their own notebook inside the `notebooks/` folder for their individual work. We will merge all findings into a main notebook or file later.
 
**At the very top of every notebook, include the following cell:**
 
```
%pip install uv
%uv sync
```
 
This ensures dependencies are always in sync when someone opens your notebook.
 
### Adding New Packages
Whenever you add a new package, use the following command instead of `pip install` so that everyone gets it automatically on their next `uv sync`:
 
```bash
uv add {package-name}
```
 
---
 
## Data
 
Taylor (or someone else) will finish the API call to download all of the data locally. All data should be stored in the `data/` folder so everyone can work from the same source.
 
> ⚠️ **Important:** Everything in the `data/` folder is excluded from GitHub by default via `.gitignore`. Do **not** push data to the repo unless you intentionally update `.gitignore`.
 
---
 
## Visualization
 
Please use **[Plotly](https://plotly.com/python/)** for all visualizations instead of Matplotlib. This is a project-wide standard requested by Taylor.
 
---
 
## Workflow Summary
 
| Task | Owner | Notes |
|---|---|---|
| API call & data download | Taylor / TBD | Data goes in `data/` folder |
| Individual analysis notebooks | Everyone | Create your own in `notebooks/` |
| Merge findings | Later | Main notebook / file TBD |
| Working & final code | Later | To be added after individual work |

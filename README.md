# TDT4225-The-Movies-Dataset

Exercise 3: Group project in TDT4225 Very Large, Distributed Data Volumes

## Requirements

- Python and Docker
- `pip install -r requirements.txt`

## Running the code

  1. Add the movies datasets to a folder  `movies_datasets`
  2. Create a `.env` file and choose passwords and username:

  ```
  MONGO_ROOT_PASSWORD=your_root_password
  MONGO_USER=your_username
  MONGO_PASSWORD=your_password
  ```

  3. Start MongoDB with `docker compose up -d`
  4. Run `eda.ipynb` for exploratory data analysis
  5. Run `data_cleaning.py` to clean the datasets
  6. Run `insert_data.py` to insert data into the MongoDB database
  7. Run `queries.py` to run the queries
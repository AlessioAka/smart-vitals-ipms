"""Make the two data files (run once, from the repository root):

    python -m simulator.make_dataset

data/patients.json            the 20-patient register the API and simulator use
data/simulated_readings.csv   TRAINING data: 80 other patients (T001..), 6 hours each

The training patients are different people from the register, so the model is
never trained on the patients it later monitors in the demo.
Everything is invented (R7): no real patient data.
"""
import json

import pandas as pd

from simulator.generator import make_patients, simulate
from src import config


def main(train_patients: int = 80, minutes: int = 360) -> None:
    register = make_patients(20, seed=7, prefix="P")
    config.PATIENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.PATIENTS_PATH.write_text(json.dumps(register, indent=2))

    training = make_patients(train_patients, seed=21, prefix="T")
    _, observed = simulate(training, minutes=minutes, seed=5, faults=True)
    df = pd.DataFrame(observed)
    df.to_csv(config.DATA_PATH, index=False)
    print(f"{len(register)} register patients -> {config.PATIENTS_PATH}")
    print(f"{len(df)} training readings from {train_patients} patients -> {config.DATA_PATH}")
    print(df["true_label"].value_counts().to_string())


if __name__ == "__main__":
    main()

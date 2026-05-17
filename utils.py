from collections import defaultdict
import os
import json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#Loading the JSON Files
def load_json(filename):
    path = os.path.join(BASE_DIR, filename)
    with open(path, "r") as f:
        return json.load(f)

#Saving the JSON Files
def save_json(data, filename):
    path = os.path.join(BASE_DIR, OUTPUT_DIR, filename)

    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, "w") as f:
        json.dump(data, f, indent=4)

"""
    Convert DISPLIB trains into a Python model:
    operation key = (train_id, operation_id)
    """
def build_operation_index(problem):

    ops = {}

    #Looping over all the trains
    for t_id, train in enumerate(problem["trains"]):
        #Looping over the operations of each train
        for o_id, op in enumerate(train):
            #Creating a key to encode the train no and operation no
            key = (t_id, o_id)
            #Storing operation data
            ops[key] = {
                "train": t_id,
                "operation": o_id,
                "start_lb": op.get("start_lb", 0),
                "start_ub": op.get("start_ub", float("inf")),
                "duration": op.get("min_duration", 0),
                "resources": [r["resource"] for r in op.get("resources", [])],
                "successors": op.get("successors", []),
            }

    return ops

#Checks the already made solution in DISPLIB
#Creating a dict for the start times of the events
"start_times[(train, operation)] = time"
def load_solution_events(solution):

    start_times = {}

    for event in solution["events"]:
        key = (event["train"], event["operation"])
        start_times[key] = event["time"]

    return start_times

#Groups operations that use the same resource together into a dict
def group_by_resource(ops):
    resource_usage = defaultdict(list)

    for key, op in ops.items():
        for resource in op["resources"]:
            resource_usage[resource].append(key)

    return resource_usage

#Function for calculating the total time for the entire operation
def total_time(ops):
    latest_start_time = 0
    total_duration = 0

    for op in ops.values():
        total_duration += op["duration"]

        if op["start_ub"] != float("inf"):
            latest_start_time = max(latest_start_time, op["start_ub"])
        else:
            latest_start_time = max(latest_start_time, op["start_lb"])

    return latest_start_time + total_duration

#Function for saving the solution file
def save_solution_file(directory_path, problem_file, solution):
    base_name = os.path.splitext(problem_file)[0]
    output_file = f"{base_name}_cp_sat_solution.json"
    output_path = os.path.join(directory_path, output_file)

    candidate = {
        "objective_value": solution["objective_value"],
        "events": solution["events"]
    }

    with open(output_path, "w") as f:
        json.dump(candidate, f, indent=2)

    return output_file

#Function for handling the multiple files
def solve_all_files(problem_directory):
    problem_path = os.path.join(BASE_DIR, problem_directory)

    for filename in os.listdir(problem_path):

        if not filename.endswith(".json"):
            continue

        print(f"\nProcessing file: {filename}")

        try:
            full_problem_file = os.path.join(problem_directory, filename)

            problem = load_json(full_problem_file)

            solution, objective = solve_problem(problem)

            output_filename = filename.replace(".json", "_solution.json")

            save_json(solution, output_filename)

            print(f"File: {filename}")
            print(f"Objective value: {objective}")
            print(f"Solution saved as: {output_filename}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            print("Continuing to next file...")
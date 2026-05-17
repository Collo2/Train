import os
import json
import subprocess

from utils import (
    build_operation_index,
    load_solution_events,
    group_by_resource,
    load_json,
    save_json
)

from cp_sat import solve_with_cp_sat


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERIFIER_FILE = os.path.join(BASE_DIR, "displib_verify.py")


# Python pre-verification before passing to displib_verify.py
def manual_check(ops, start_times):

    errors = []

    # 1. Check time bounds
    for key, op in ops.items():
        if key not in start_times:
            continue

        s = start_times[key]

        if s < op["start_lb"]:
            errors.append(f"{key} violates start_lb: {s} < {op['start_lb']}")

        if op["start_ub"] != float("inf") and s > op["start_ub"]:
            errors.append(f"{key} violates start_ub: {s} > {op['start_ub']}")

    # 2. Check precedence constraints
    for (t_id, o_id), op in ops.items():
        if (t_id, o_id) not in start_times:
            continue

        s_current = start_times[(t_id, o_id)]
        end_current = s_current + op["duration"]

        for succ in op["successors"]:
            succ_key = (t_id, succ)

            if succ_key not in start_times:
                continue

            s_successor = start_times[succ_key]

            if s_successor < end_current:
                errors.append(
                    f"Precedence violation: train {t_id}, op {o_id} ends at "
                    f"{end_current}, but successor op {succ} starts at {s_successor}"
                )

    # 3. Check resource conflicts
    resource_usage = group_by_resource(ops)

    for resource, keys in resource_usage.items():
        intervals = []

        for key in keys:
            if key not in start_times:
                continue

            s = start_times[key]
            e = s + ops[key]["duration"]
            intervals.append((s, e, key))

        intervals.sort()

        for i in range(len(intervals) - 1):
            s1, e1, key1 = intervals[i]
            s2, e2, key2 = intervals[i + 1]

            if e1 > s2:
                errors.append(
                    f"Resource conflict on {resource}: {key1} [{s1}, {e1}) "
                    f"overlaps {key2} [{s2}, {e2})"
                )

    return errors


# Function for writing the solution into a JSON file
def write_candidate_solution(solution, output_file):

    candidate = {
        "events": solution["events"]
    }

    if "objective_value" in solution:
        candidate["objective_value"] = solution["objective_value"]

    with open(output_file, "w") as f:
        json.dump(candidate, f, indent=2)

    return output_file


# Solving using displib_verify.py
def run_official_verifier(problem_file, solution_file):

    result = subprocess.run(
        ["python", VERIFIER_FILE, problem_file, solution_file],
        text=True,
        capture_output=True
    )

    print(result.stdout)

    if result.stderr:
        print(result.stderr)

    return result.returncode


def main():

    problem_dir = "problem_set"
    problem_path = os.path.join(BASE_DIR, problem_dir)

    count = 0

    for filename in os.listdir(problem_path):

        if not filename.endswith(".json"):
            continue

        problem_file = os.path.join(problem_dir, filename)

        print("\n==============================")
        print(f"Processing problem: {filename}")
        print("==============================")

        try:
            problem = load_json(problem_file)

            ops = build_operation_index(problem)

            print(f"Loaded {len(problem['trains'])} trains")
            print(f"Loaded {len(ops)} operations")

            # Solve using CP-SAT
            solution = solve_with_cp_sat(problem, time_limit=60)

            if solution is None:
                print(f"No feasible solution found for {filename}")
                continue

            start_times = load_solution_events(solution)

            print(f"Generated {len(solution['events'])} solution events")

            # Count successful CP-SAT solves with objective value
            if "objective_value" in solution:
                print(f"Objective value: {solution['objective_value']}")

                count += 1

                print(f"Successful solves so far: {count}")

            else:
                print("Objective value not found in solution")
                continue

            # Manual checking
            errors = manual_check(ops, start_times)

            if errors:
                print("\nManual model check found errors:")

                for err in errors[:20]:
                    print(" -", err)

                if len(errors) > 20:
                    print(f"... and {len(errors) - 20} more errors")

                continue

            else:
                print("\nManual model check passed.")

            # Save candidate solution
            output_filename = filename.replace(".json", "_candidate_solution.json")
            output_file = os.path.join(BASE_DIR, output_filename)

            candidate_file = write_candidate_solution(solution, output_file)

            # Official verifier
            print("\nRunning official DISPLIB verifier...\n")

            code = run_official_verifier(problem_file, candidate_file)

            if code == 0:
                print(f"Official verification passed for {filename}")
            else:
                print(f"Official verification failed for {filename}")

        except Exception as e:
            print(f"Error processing {filename}: {e}")
            print("Continuing to next file...")

    print("\n==============================")
    print(f"Total successful CP-SAT solves with objective value: {count}")
    print("==============================")


if __name__ == "__main__":
    main()
from ortools.sat.python import cp_model
from utils import build_operation_index, group_by_resource, total_time


def solve_with_cp_sat(problem, time_limit=120):
    ops = build_operation_index(problem)
    resource_usage = group_by_resource(ops)

    horizon = int(total_time(ops))

    model = cp_model.CpModel()

    start = {}
    end = {}
    delay = {}

    # Defining the variables
    for key, op in ops.items():
        lb = int(op["start_lb"])
        ub = horizon if op["start_ub"] == float("inf") else int(op["start_ub"])

        start[key] = model.NewIntVar(lb, ub, f"start_t{key[0]}_o{key[1]}")
        end[key] = model.NewIntVar(0, horizon, f"end_t{key[0]}_o{key[1]}")

        model.Add(end[key] == start[key] + int(op["duration"]))

    # Precedence constraints
    for key, op in ops.items():
        t_id, o_id = key

        for succ in op["successors"]:
            succ_key = (t_id, succ)
            model.Add(start[succ_key] >= end[key])

    # Resource constraints
    for resource, keys in resource_usage.items():
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a = keys[i]
                b = keys[j]

                if a[0] == b[0]:
                    continue

                a_before_b = model.NewBoolVar(f"{resource}_{a}_before_{b}")

                model.Add(end[a] <= start[b]).OnlyEnforceIf(a_before_b)
                model.Add(end[b] <= start[a]).OnlyEnforceIf(a_before_b.Not())

    # Objective: minimize total delay
    for key, op in ops.items():
        threshold = int(op["start_lb"]) + int(op["duration"])
        finish_time = end[key]

        delay[key] = model.NewIntVar(
            0,
            horizon,
            f"delay_t{key[0]}_o{key[1]}"
        )

        model.Add(delay[key] >= finish_time - threshold)

    total_delay = model.NewIntVar(
        0,
        horizon * len(ops),
        "total_delay"
    )

    model.Add(total_delay == sum(delay.values()))

    model.Minimize(total_delay)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        print("No feasible solution found.")
        return None

    events = []

    for key in ops:
        events.append({
            "train": key[0],
            "operation": key[1],
            "time": solver.Value(start[key])
        })

    events.sort(key=lambda e: (e["time"], e["train"], e["operation"]))

    solution = {
        "objective_value": int(solver.ObjectiveValue()),
        "total_delay": solver.Value(total_delay),
        "events": events
    }

    print("CP-SAT status:", solver.StatusName(status))
    print("CP-SAT total delay:", solution["total_delay"])

    return solution
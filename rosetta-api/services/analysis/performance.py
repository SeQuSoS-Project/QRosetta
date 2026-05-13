def create_performance_report(results_list: list) -> dict:
    """
    Generates a report on the execution time of each simulator.
    """
    performance_data = []
    
    for res in results_list:
        sim_name = res.get('simulator', 'unknown')
        
        if 'error' in res:
            performance_data.append({
                "simulator": sim_name,
                "status": "error",
                "error": res['error'], # Include the error message
                "execution_time_sec": None
            })
        elif 'execution_time_sec' in res:
            performance_data.append({
                "simulator": sim_name,
                "status": "success",
                "execution_time_sec": res['execution_time_sec'],
                "compilation_time_sec": res.get('compilation_time_sec'),
                "simulation_time_sec": res.get('simulation_time_sec')
            })
    
    # Sort the list by execution time (fastest first)
    sorted_data = sorted(
        performance_data, 
        key=lambda x: (x['execution_time_sec'] is None, x['execution_time_sec'])
    )
    
    return {
        "summary": "Execution time in seconds (fastest first).",
        "ranking": sorted_data
    }

def create_resource_report(results_list: list) -> dict:
    """
    Generates a report on the memory usage of each simulator.
    """
    resource_data = []
    
    for res in results_list:
        sim_name = res.get('simulator', 'unknown')
        
        if 'error' in res:
            resource_data.append({
                "simulator": sim_name,
                "status": "error",
                "error": res['error'], # Include the error message
                "memory_usage_mb": None,
                "process_peak_mb": None
            })
        else:
            resource_data.append({
                "simulator": sim_name,
                "status": "success",
                "memory_usage_mb": res.get('memory_usage_mb'),
                "process_peak_mb": res.get('process_peak_mb'),
                "theoretical_statevector_mb": res.get('theoretical_statevector_mb')
            })

    # Sort the list by memory usage (lowest first)
    sorted_data = sorted(
        resource_data,
        key=lambda x: (x['memory_usage_mb'] is None, x['memory_usage_mb'])
    )

    return {
        "summary": "Memory usage delta in MiB (lowest first).",
        "ranking": sorted_data
    }

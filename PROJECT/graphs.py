import pandas as pd
import matplotlib.pyplot as plt
from types import SimpleNamespace
import os
from analytics import AttendanceAnalytics

def generate_graphs_and_stats(filepath):
    try:
        # Use the AttendanceAnalytics class for consistency
        analytics = AttendanceAnalytics(filepath)
        
        # Generate the basic graphs
        analytics.generate_enhanced_graphs()
        
        # Get the summary statistics
        stats = analytics.get_summary_statistics()
        
        if stats is None:
            return None
            
        # Add the top_3 and bottom_3 attributes for backward compatibility
        student_trends = stats.student_trends
        if not student_trends:
            return None
            
        sorted_students = sorted(student_trends.items(), key=lambda x: x[1]['attendance_rate'], reverse=True)
        
        stats.top_3 = [(name, data['attendance_rate']) for name, data in sorted_students[:3]]
        stats.bottom_3 = [(name, data['attendance_rate']) for name, data in sorted_students[-3:]]
        
        return stats
        
    except Exception as e:
        print(f"Error in generate_graphs_and_stats: {str(e)}")  # For debugging
        return None

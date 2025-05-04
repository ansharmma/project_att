import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from types import SimpleNamespace
import os

class AttendanceAnalytics:
    def __init__(self, filepath):
        self.df = pd.read_csv(filepath)
        self.student_names = self.df['Name']
        self.dates = self.df.columns[1:]
        self.attendance_data = self.df.iloc[:, 1:]
        
    def get_monthly_attendance(self):
        """Calculate monthly attendance statistics"""
        monthly_stats = {}
        for date in self.dates:
            month = datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m')
            if month not in monthly_stats:
                monthly_stats[month] = {'present': 0, 'total': 0}
            monthly_stats[month]['total'] += len(self.student_names)
            monthly_stats[month]['present'] += sum(self.attendance_data[date].str.upper() == 'P')
        
        return {month: (stats['present']/stats['total']*100) 
                for month, stats in monthly_stats.items()}
    
    def get_attendance_patterns(self):
        """Analyze attendance patterns by day of week"""
        day_patterns = {}
        for date in self.dates:
            day = datetime.strptime(date, '%Y-%m-%d').strftime('%A')
            if day not in day_patterns:
                day_patterns[day] = {'present': 0, 'total': 0}
            day_patterns[day]['total'] += len(self.student_names)
            day_patterns[day]['present'] += sum(self.attendance_data[date].str.upper() == 'P')
        
        return {day: (stats['present']/stats['total']*100) 
                for day, stats in day_patterns.items()}
    
    def get_student_trends(self):
        """Calculate attendance trends for each student"""
        trends = {}
        for idx, student in enumerate(self.student_names):
            attendance = self.attendance_data.iloc[idx]
            present_days = sum(attendance.str.upper() == 'P')
            total_days = len(self.dates)
            trends[student] = {
                'attendance_rate': (present_days/total_days*100),
                'total_present': present_days,
                'total_absent': total_days - present_days
            }
        return trends
    
    def get_student_data(self, student_name):
        """Get detailed data for a specific student"""
        # Find the student index
        student_idx = None
        for idx, name in enumerate(self.student_names):
            if name == student_name:
                student_idx = idx
                break
                
        if student_idx is None:
            return None
            
        # Get student's attendance data
        attendance = self.attendance_data.iloc[student_idx]
        present_days = sum(attendance.str.upper() == 'P')
        total_days = len(self.dates)
        attendance_rate = (present_days/total_days*100)
        
        # Create attendance calendar
        attendance_calendar = {}
        for date in self.dates:
            attendance_calendar[date] = attendance[date]
            
        # Calculate monthly performance
        monthly_performance = {}
        for date in self.dates:
            month = datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m')
            if month not in monthly_performance:
                monthly_performance[month] = {'present': 0, 'total': 0}
            monthly_performance[month]['total'] += 1
            if attendance[date].upper() == 'P':
                monthly_performance[month]['present'] += 1
                
        # Calculate rates for each month
        for month in monthly_performance:
            total = monthly_performance[month]['total']
            present = monthly_performance[month]['present']
            monthly_performance[month]['rate'] = (present/total*100)
            monthly_performance[month]['absent'] = total - present
        
        # Create student data object
        student_data = SimpleNamespace()
        student_data.name = student_name
        student_data.attendance_rate = attendance_rate
        student_data.total_present = present_days
        student_data.total_absent = total_days - present_days
        student_data.attendance_calendar = attendance_calendar
        student_data.monthly_performance = monthly_performance
        
        return student_data
    
    def generate_enhanced_graphs(self):
        """Generate additional analytical graphs"""
        # Ensure static directory exists
        os.makedirs("static", exist_ok=True)
        
        # Calculate basic statistics
        present_count = self.attendance_data.apply(lambda row: sum(val.upper() == 'P' for val in row), axis=1)
        total_classes = len(self.dates)
        attendance_percent = (present_count / total_classes * 100).round(2)
        
        # Generate basic graphs (from the original graphs.py)
        # Bar Chart
        plt.figure(figsize=(10, 5))
        plt.bar(self.student_names, attendance_percent, color='skyblue')
        plt.xticks(rotation=45, ha='right')
        plt.title("Student Attendance %")
        plt.ylabel("Percentage")
        plt.tight_layout()
        plt.savefig("static/attendance_percent_chart.png")
        plt.close()

        # Line Chart
        plt.figure(figsize=(10, 5))
        plt.plot(self.student_names, attendance_percent, marker='o', color='green')
        plt.xticks(rotation=45, ha='right')
        plt.title("Attendance Trend")
        plt.ylabel("Percentage")
        plt.tight_layout()
        plt.savefig("static/attendance_trend_line.png")
        plt.close()

        # Pie Chart
        total_present = present_count.sum()
        total_absent = total_classes * len(self.student_names) - total_present
        plt.figure(figsize=(6, 6))
        plt.pie([total_present, total_absent], labels=["Present", "Absent"],
                autopct='%1.1f%%', colors=["#4CAF50", "#F44336"])
        plt.title("Overall Attendance")
        plt.savefig("static/overall_attendance_pie.png")
        plt.close()
        
        # Generate enhanced graphs
        # Monthly attendance trend
        monthly_stats = self.get_monthly_attendance()
        plt.figure(figsize=(12, 6))
        plt.plot(list(monthly_stats.keys()), list(monthly_stats.values()), marker='o')
        plt.title('Monthly Attendance Trend')
        plt.xlabel('Month')
        plt.ylabel('Attendance Rate (%)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('static/monthly_attendance_trend.png')
        plt.close()
        
        # Day-wise attendance pattern
        day_patterns = self.get_attendance_patterns()
        plt.figure(figsize=(10, 6))
        plt.bar(day_patterns.keys(), day_patterns.values())
        plt.title('Attendance by Day of Week')
        plt.xlabel('Day')
        plt.ylabel('Attendance Rate (%)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('static/day_wise_attendance.png')
        plt.close()
        
        # Student attendance heatmap
        plt.figure(figsize=(15, 8))
        attendance_matrix = self.attendance_data.applymap(lambda x: 1 if x.upper() == 'P' else 0)
        sns.heatmap(attendance_matrix, cmap='RdYlGn', 
                   xticklabels=True, yticklabels=self.student_names)
        plt.title('Student Attendance Heatmap')
        plt.xlabel('Date')
        plt.ylabel('Student')
        plt.tight_layout()
        plt.savefig('static/attendance_heatmap.png')
        plt.close()
        
        # Save summary report
        summary_df = pd.DataFrame({
            'Name': self.student_names,
            'Present': present_count,
            'Attendance (%)': attendance_percent
        })
        summary_df.to_csv("static/attendance_report.csv", index=False)
    
    def get_summary_statistics(self):
        """Get comprehensive summary statistics"""
        student_trends = self.get_student_trends()
        monthly_stats = self.get_monthly_attendance()
        day_patterns = self.get_attendance_patterns()
        
        stats = SimpleNamespace()
        stats.total_students = len(self.student_names)
        stats.average_attendance = np.mean([trend['attendance_rate'] 
                                          for trend in student_trends.values()])
        stats.monthly_stats = monthly_stats
        stats.day_patterns = day_patterns
        stats.student_trends = student_trends
        
        # Calculate additional metrics
        stats.most_consistent_day = max(day_patterns.items(), key=lambda x: x[1])[0]
        stats.least_consistent_day = min(day_patterns.items(), key=lambda x: x[1])[0]
        stats.best_month = max(monthly_stats.items(), key=lambda x: x[1])[0]
        stats.worst_month = min(monthly_stats.items(), key=lambda x: x[1])[0]
        
        return stats 
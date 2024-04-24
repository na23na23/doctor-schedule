from datetime import datetime, timedelta
import csv
import random
import pandas as pd
import streamlit as st

class Month:
    def __init__(self, doctors, weekends, start_day, num_of_days_in_month, unavailable_sessions_days={}, unavailable_standby_days={}, unavailable_clinic_days=[], holidays=[]):
        """
        Initializes the Month class with a dictionary of doctors, days considered as weekends, and the weekday of the first day of the month.
        :param doctors: dict, a dictionary of doctor names and their types ('regular' or 'special')
        :param weekends: list, days of the week considered as weekends (0=Sunday, 1=Monday, ..., 6=Saturday)
        :param start_day: int, the weekday of the first day of the month (0=Sunday, 1=Monday, ..., 6=Saturday)
        :param unavailable_sessions_days, unavailable_standby_days, unavailable_clinic_days: dict, a dictionary where keys are doctor names and values are lists of days they are unavailable
        :param holidays: list, dates of the month that sessions are not scheduled
        """
        self.doctors = doctors
        self.weekends = weekends
        self.start_day = start_day
        self.num_of_days_in_month = num_of_days_in_month+1
        self.unavailable_sessions_days = unavailable_sessions_days
        self.unavailable_standby_days = unavailable_standby_days
        self.unavailable_clinic_days = unavailable_clinic_days
        self.holidays = holidays
        self.schedule = {day: None for day in range(1, self.num_of_days_in_month)}
        self.standby = {day: None for day in range(1, self.num_of_days_in_month)}

    def is_weekday(self, day):
        # Calculate day of the week for this date
        day_of_week = (self.start_day + day - 1) % 7
        return day_of_week not in self.weekends

    def assign_sessions(self):
        # Gather doctors
        regulars = [name for name, type_ in self.doctors.items() if type_ == 'regular']
        specials = [name for name, type_ in self.doctors.items() if type_ == 'special']

        # Set required sessions counts
        coronary_first = {name: 3 if name == "Hana" else 2 for name in regulars}
        coronary_second = {name: 2 for name in regulars}
        tavi_first = {name: 1 for name in regulars}
        tavi_second = {name: 1 for name in regulars}

        # Filter days for session assignment (only weekdays)
        days = [i for i in range(1, self.num_of_days_in_month) if self.is_weekday(i)]

        random.shuffle(days)
        half_point = len(days) // 2

        for i, day in enumerate(days):
            if day in self.holidays:
                continue
            session_type = 'coronary' if i < half_point else 'TAVI'
            first, second = (coronary_first, coronary_second) if session_type == 'coronary' else (tavi_first, tavi_second)

            first_candidates = [doc for doc in first if first[doc] > 0]
            second_candidates = [doc for doc in second if second[doc] > 0]

            if not first_candidates or not second_candidates:
                continue

            chosen_first, chosen_second = None, None
            while chosen_first == None or chosen_second == None:
                first_candidate = random.choice(first_candidates)
                second_candidate = None#random.choice([doc for doc in second_candidates if doc != chosen_first])

                attempts = 0
                while True:
                    second_candidate = random.choice(second_candidates)
                    if (second_candidate != chosen_first and second_candidate != first_candidate) or attempts > 1000:
                        break
                    attempts += 1

                if chosen_first == None:
                    if day not in self.unavailable_sessions_days.get(first_candidate, []):
                        chosen_first = first_candidate

                if chosen_second == None:
                    if day not in self.unavailable_sessions_days.get(second_candidate, []):
                        chosen_second = second_candidate

            self.schedule[day] = (session_type, chosen_first, chosen_second)
            first[chosen_first] -= 1
            second[chosen_second] -= 1

    def assign_standby(self):
        # Gather doctor types
        regulars = [name for name, type_ in self.doctors.items() if type_ == 'regular']
        specials = [name for name, type_ in self.doctors.items() if type_ == 'special']
        specials.remove("Greenberg") # Greenberg only available for sessions, not standbys
        specials.remove("Katya") # Katya only available for sessions, not standbys

        # Initialize the standby requirement counts
        standby_counts = {name: 5 for name in regulars}
        standby_counts["Hana"] = 4  # Hana prefers only one Saturday

        # Assign weekends first for regular doctors
        saturdays = [i for i in range(1, self.num_of_days_in_month) if (self.start_day + i - 1) % 7 == 6]
        fridays = [i for i in range(1, self.num_of_days_in_month) if (self.start_day + i - 1) % 7 == 5]

        # Assign Hana to one Saturday if possible
        if saturdays:
            for i, saturday in enumerate(saturdays):
                if not saturday in self.unavailable_standby_days.get("Hana", []):
                    self.standby[saturdays[i]] = "Hana"
                    standby_counts["Hana"] -= 1
                    saturdays.pop(i)
                    break

        # Assign other doctors to full weekends
        for friday, saturday in zip(fridays, saturdays):
            for name in regulars:
                if name == "Hana":
                    continue  # Skip Hana for additional Saturdays
                if standby_counts[name] >= 2 and friday not in self.unavailable_standby_days.get(name, []) and saturday not in self.unavailable_standby_days.get(name, []):
                    self.standby[friday] = name
                    self.standby[saturday] = name
                    standby_counts[name] -= 2
                    break

        # Assign remaining standby shifts on weekdays
        weekdays = [i for i in range(1, self.num_of_days_in_month) if self.is_weekday(i)]
        for day in weekdays:
            random.shuffle(regulars)
            if all(count <= 0 for count in standby_counts.values()):
                break  # Stop if all standby requirements are met
            for name in regulars:
                if standby_counts[name] > 0 and self.standby[day] is None and day not in self.unavailable_standby_days.get(name, []):
                    self.standby[day] = name
                    standby_counts[name] -= 1
                    break

        # Fill in any remaining slots with special doctors as needed
        for day in range(1, self.num_of_days_in_month):
            if self.standby[day] is None:
                self.standby[day] = random.choice(specials)


    def generate_schedule(self):
        self.assign_sessions()
        self.assign_standby()

        clinic_days = random.sample([day for day in range(1, self.num_of_days_in_month) if self.is_weekday(day) if day not in self.unavailable_clinic_days], 3)
        clinic_assignments = {}
        count = {'Perl': 0, 'Amos': 0}
        for day in clinic_days:
            if count['Perl'] == count['Amos']:
                chosen = random.choice(['Perl', 'Amos'])
            elif count['Perl'] < count['Amos']:
                chosen = 'Perl'
            else:
                chosen = 'Amos'
            clinic_assignments[day] = chosen
            count[chosen] += 1
        rows = []

        for day in range(1, self.num_of_days_in_month):
            session_info = self.schedule.get(day)
            standby_doctor = self.standby.get(day)
            clinic_doctor = clinic_assignments.get(day, '')  # Get clinic doctor if assigned, else 'None'
            
            if session_info:
                # Extract session type and doctors assigned to the session
                session_type, first_doctor, second_doctor = session_info
            else:
                # If no session is scheduled, write empty placeholders
                session_type, first_doctor, second_doctor = '', '', ''
            
            # Write the day's schedule to the file
            rows.append([day, session_type, first_doctor, second_doctor, standby_doctor or '', clinic_doctor])
        
        df = pd.DataFrame(rows, columns=['Day', 'Session Type', 'First Doctor', 'Second Doctor', 'Standby Doctor', 'Clinic'])
        return df

### App
st.title('Doctors Schedule Generator')
cols = st.columns(2)

# User inputs for the schedule
num_of_days_in_month = cols[0].number_input('Number of days in the month', min_value=28, max_value=31, value=30)
start_day = cols[1].selectbox('What day of the week does the month start on?', ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'])
#weekends = st.multiselect('Select weekend days', ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'], default=['Saturday', 'Sunday'])

# Convert start day and weekends to numeric values
start_day_num = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].index(start_day)
#weekend_nums = [ ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].index(day) for day in weekends ]

# Doctor definitions
#doctors_input = st.text_area("Enter doctors and their types as 'name:type', separated by commas. Example: 'Hana:regular, Pablo:special'", 'Hana:regular, Pablo:special')
#doctors = {name.strip(): type_.strip() for name, type_ in (doctor.split(':') for doctor in doctors_input.split(','))}
doctors = {"Hana": "regular", "Pablo": "regular", "Amos": "regular", "Wittberg": "regular",
    "Perl": "regular", "Giorgi": "special", "Mark": "special", "Kornovsky": "special",
    "Hasdai": "special", "Greenberg": "special", "Katya": "special"}

# Unavailable days inputs
unavailable_sessions_days, unavailable_standby_days, unavailable_clinic_days, holidays = {}, {}, [], []

for doctor in doctors:
    # Create a multiselect for unavailable session days
    selected_sessions_days = cols[0].multiselect(
        f"Unavailable session days for {doctor}:",
        range(1, num_of_days_in_month+1),
        key=f"{doctor}_sessions"
    )
    unavailable_sessions_days[doctor] = selected_sessions_days
    
    # Create a multiselect for unavailable standby days
    selected_standby_days = cols[1].multiselect(
        f"Unavailable standby days for {doctor}:",
        range(1, num_of_days_in_month+1),
        key=f"{doctor}_standby"
    )
    unavailable_standby_days[doctor] = selected_standby_days

unavailable_clinic_days = cols[0].multiselect("Unavailable clinic days:", range(1, num_of_days_in_month+1), key="clinic")
holidays = cols[1].multiselect("Enter holidays:", range(1, num_of_days_in_month+1), key="holidays")

if st.button('Generate Schedule'):
    month = Month(doctors=doctors, weekends=[5, 6], start_day=start_day_num, num_of_days_in_month=num_of_days_in_month, unavailable_sessions_days=unavailable_sessions_days, unavailable_standby_days=unavailable_standby_days, unavailable_clinic_days=unavailable_clinic_days, holidays=holidays)
    df = month.generate_schedule()

    html = df.to_html(index=False)
    st.markdown(html, unsafe_allow_html=True)

from datetime import datetime

UA_WEEKDAYS = {
    'Mon': 'Пн',
    'Tue': 'Вт',
    'Wed': 'Ср',
    'Thu': 'Чт',
    'Fri': 'Пт',
    'Sat': 'Сб',
    'Sun': 'Нд',
}

UA_MONTHS = {
    '01': 'січ',
    '02': 'лют',
    '03': 'бер',
    '04': 'квіт',
    '05': 'трав',
    '06': 'черв',
    '07': 'лип',
    '08': 'серп',
    '09': 'вер',
    '10': 'жовт',
    '11': 'лист',
    '12': 'груд',
}

def format_date_label(date_obj: datetime) -> str:
    dow = UA_WEEKDAYS[date_obj.strftime('%a')]  # Пн, Вт, ...
    day = date_obj.strftime('%d')               # 01–31
    month = UA_MONTHS[date_obj.strftime('%m')]  # січ, лют, ...
    return f"{dow}, {day} {month}"

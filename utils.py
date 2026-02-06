def bmr_mifflin(sex, weight, height, age):
    if sex == "M":
        return 10*weight + 6.25*height - 5*age + 5
    return 10*weight + 6.25*height - 5*age - 161

def tdee(bmr, activity_level):
    factors = {
        "sedentario": 1.2,
        "leggero": 1.375,
        "moderato": 1.55,
        "alto": 1.725
    }
    return bmr * factors.get(activity_level, 1.375)
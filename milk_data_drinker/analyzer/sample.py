def yesno(response):
    if response.lower() == "y":
        return True
    else:
        return False


class Macronutrient:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class Replicate:
    def __init__(self, name, macronutrients):
        self.name = name
        self.macronutrients = macronutrients
        self.mean_flag = False
        self.stddev_flag = False
        self.reference_flag = False
        self.difference_flag = False
        if not name.isnumeric():
            self.set_flags()

    def __str__(self):
        return f"Replicate {self.name}: {len(self.macronutrients)} macronutrients."

    def add_macronutrient(self, macronutrient):
        if macronutrient is None:
            print(f"Replicate {self.name}: No macronutrient to add")
        self.macronutrients.append(macronutrient)

    def set_flags(self):
        self.mean_flag = self.name.lower() == "mean"
        self.stddev_flag = self.name.lower() == "stddev"
        self.reference_flag = self.name.lower() == "reference"
        self.difference_flag = self.name.lower() == "difference"


class Sample:
    def __init__(self, name, type, date, replicates):
        self.name = name
        self.type = type
        self.date = date
        self.replicates = replicates
        self.mean_replicate = None
        self.stddev_replicate = None
        self.reference_replicate = None
        self.difference_replicate = None
        self.set_special_replicates()

    def __str__(self):
        return f"{self.name} {self.date}: {len(self.replicates)} replicates."

    def add_replicate(self, replicate):
        if replicate is None:
            print(f"{self.name}: No replicate to add.")
            return
        self.replicates.append(replicate)
        if replicate.name.lower() == "mean":
            self.set_mean_replicate(replicate)
            return
        if replicate.name.lower() == "stddev":
            self.set_stddev_replicate(replicate)
            return
        if replicate.name.lower() == "difference":
            self.set_difference_replicate(replicate)
            return
        if replicate.name.lower() == "reference":
            self.set_reference_replicate(replicate)
            return

    def set_special_replicates(self):
        if self.mean_replicate is None:
            self.set_mean_replicate(self.find_mean_replicate())
        if self.stddev_replicate is None:
            self.set_stddev_replicate(self.find_stddev_replicate())
        if self.reference_replicate is None:
            self.set_reference_replicate(self.find_reference_replicate())
        if self.difference_replicate is None:
            self.set_difference_replicate(self.find_difference_replicate())

    def find_mean_replicate(self):
        for replicate in self.replicates:
            if replicate.name.lower() == "mean":
                return replicate
        return None

    def find_stddev_replicate(self):
        for replicate in self.replicates:
            if replicate.name.lower() == "stddev":
                return replicate
        return None

    def find_difference_replicate(self):
        for replicate in self.replicates:
            if replicate.name.lower() == "difference":
                return replicate
        return None

    def find_reference_replicate(self):
        for replicate in self.replicates:
            if replicate.name.lower() == "reference":
                return replicate
        return None

    def set_mean_replicate(self, replicate):
        self.mean_replicate = replicate

    def set_stddev_replicate(self, replicate):
        self.stddev_replicate = replicate

    def set_reference_replicate(self, replicate):
        self.reference_replicate = replicate

    def set_difference_replicate(self, replicate):
        self.difference_replicate = replicate

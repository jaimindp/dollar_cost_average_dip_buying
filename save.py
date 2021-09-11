from datetime import datetime


# Converts an object to a json safe dictionary for saving
def save_obj(obj):

	# If the type is a tuple or a set
	if isinstance(obj, (tuple, set)):
		obj = list(obj)
	
	# If this is a dict itself
	elif isinstance(obj, (dict)):
		new_dict = {}
		for k,v in obj.items():
			if k != 'func':
				new_dict[k] = save_obj(v)
		for k,v in new_dict.items():
			obj[k] = v
		if 'func' in obj:
			obj.pop('func')

	# If this object can be converted to a dict
	elif hasattr(obj, '__dict__'):
		to_pop = []
		for k,v in obj.__dict__.items():
			if isinstance(v, (dict, int, float, set, list, tuple, dict, bool, str, datetime)):
				setattr(obj, k, save_obj(v))
			elif v is None:
				setattr(obj, k, None)
			else:
				to_pop.append(k)
		for i in to_pop:
			delattr(obj, i)

	# Convert this object if it is a datetime
	elif isinstance(obj, (datetime)):
		return obj.isoformat()

	# If this object is iterable (list)
	elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
		for i, child in enumerate(obj):
			obj[i] = save_obj(child)

	return obj


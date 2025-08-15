import c4d

def get_hierarchy_path(obj, sep="/"):
	path = []
	while obj:
		path.insert(0, obj.GetName())
		obj = obj.GetUp()
	return sep.join(path[:-1])  # 不包含自身，只包含父级路径

def get_or_create_layer(doc, layer_name):
	layer_root = doc.GetLayerObjectRoot()
	layer = layer_root.GetDown()
	while layer:
		if layer.GetName() == layer_name:
			return layer
		layer = layer.GetNext()
	# 没有则新建
	layer = c4d.documents.LayerObject()
	layer.SetName(layer_name)
	doc.InsertLayerObject(layer)
	return layer

def main():
	doc = c4d.documents.GetActiveDocument()
	def traverse(obj):
		while obj:
			path = get_hierarchy_path(obj)
			if path:
				layer = get_or_create_layer(doc, path)
				obj.SetLayerObject(doc, layer)
			traverse(obj.GetDown())
			obj = obj.GetNext()
	traverse(doc.GetFirstObject())
	c4d.EventAdd()

if __name__=='__main__':
	main()

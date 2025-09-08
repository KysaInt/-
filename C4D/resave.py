import c4d
import os

def main():
    # 获取当前活动文档
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        c4d.gui.MessageDialog("没有活动的文档。")
        return
    
    # 获取文档路径
    doc_path = doc.GetDocumentPath()
    if not doc_path:
        c4d.gui.MessageDialog("文档未保存，请先保存文档。")
        return
    
    # 构建输出路径为文档目录下的 "0/" 文件夹
    output_dir = os.path.join(doc_path, "0")
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 获取渲染数据
    render_data = doc.GetActiveRenderData()
    
    # 设置输出路径
    render_data[c4d.RDATA_PATH] = output_dir
    
    # 更新文档
    c4d.EventAdd()
    
    c4d.gui.MessageDialog("输出路径已设置为: " + output_dir)

if __name__ == '__main__':
    main()

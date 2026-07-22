// 底部固定操作栏：长表单页面（自评/评估/校准）的保存/提交入口
// 56px 高，适配 iPhone 安全区；页面容器需同时加 .has-bottom-actions 腾出空间
interface BottomActionsProps {
  children: React.ReactNode;
}

const BottomActions: React.FC<BottomActionsProps> = ({ children }) => (
  <div className="form-bottom-actions">{children}</div>
);

export default BottomActions;

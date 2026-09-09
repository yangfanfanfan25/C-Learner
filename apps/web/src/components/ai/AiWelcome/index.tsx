import styles from './index.module.less';

/** 空会话欢迎区（背景图 + 欢迎语） */
const AiWelcome: React.FC = () => {
  return (
    <div className={styles.welcome}>
      <div className={styles.icon}>
        <img src="/C-Learner_owl_icon.svg" alt="C-Learner 智能体" />
      </div>
      <h2>时间与自己是最好的老师</h2>
    </div>
  );
};

export default AiWelcome;

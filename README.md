# Pose Estimation Repository

Welcome to the Pose Estimation repository! This repository contains an implementation of various pose estimation models customized to facilitate research at the master's level. The provided tools can be utilized to train a multi-person pose estimation model on a custom dataset. Below, we outline the steps required to train and test the model effectively.

## Step 1: Data Labeling

To train the model effectively, labeled data containing pose information is essential. Manual labeling can be challenging and time-consuming. To simplify this process, we leverage the AlphaPose pose estimation model for data labeling.

### Instructions:

1. **Prepare Images:** Organize all images in a designated folder.
2. **Run AlphaPose:** Utilize the following command within the AlphaPose directory:

```bash
python scripts/demo_inference.py --cfg ${cfg_file} --checkpoint ${trained_model} --indir ${img_directory} --outdir ${output_directory}
 ```

#### Parameters:
- `--cfg`: Configuration file corresponding to the chosen trained model.
- `--checkpoint`: Trained model for pose estimation. Models are available [here](https://github.com/saqib736/Pose_Estimation/blob/main/AlphaPose/docs/MODEL_ZOO.md#model-zoo).
- `--indir`: Input image folder.
- `--outdir`: Output directory for results.

For more detailed inference options and examples, please refer to the [AlphaPose documentation](https://github.com/saqib736/Pose_Estimation/blob/main/AlphaPose/docs/GETTING_STARTED.md#getting-started).

By default, the results for all images will be saved in one JSON file, following the format used by COCO. Detailed information regarding output format can be found [here](https://github.com/saqib736/Pose_Estimation/blob/main/AlphaPose/docs/output.md#contents).

## Step 2: Model Training

Once labeled pose data in JSON format is available, we can proceed to train different models such as OpenPose, PifPaf, and Pose Proposal, as present under the `hyperpose` directory. These models have been customized to align with specific research objectives.

### Instructions:

1. **Data Preparation:** Organize data in image format into three folders: `train`, `validation`, and `testset`. Save corresponding labels in separate directories as annotations. Detailed dataset preparation guidelines can be found in the [HyperPose documentation](https://hyperpose.readthedocs.io/en/latest/).

2. **Training and Evaluation:**
   - Utilize `train.py` to train the models.
   - Use `eval.py` to evaluate model performance.
   - Employ `python_demo.py` for testing the models.

Ensure adherence to the documentation for seamless execution of training, evaluation, and testing processes.

Thank you for choosing our Pose Estimation repository. For any further inquiries or assistance, feel free to reach out. Happy coding!

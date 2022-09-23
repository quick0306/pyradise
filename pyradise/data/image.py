from abc import (
    ABC,
    abstractmethod)
from typing import (
    Any,
    Tuple,
    Union,
    Optional,
    TypeVar)
from copy import deepcopy

import SimpleITK as sitk
import itk
import numpy as np

from .modality import Modality
from .organ import (
    Organ,
    OrganRaterCombination)
from .rater import Rater
from .taping import TransformTape
from ..utils import (convert_to_itk_image, convert_to_sitk_image)

TransformInfo = TypeVar('TransformInfo')

__all__ = ['Image', 'IntensityImage', 'SegmentationImage', 'ImageProperties']


class ImageProperties:
    """A class to store image properties. This class is predominantly used in combination with a
    :class:`~pyradise.data.taping.TransformTapeV2` to keep track of the image properties before or after a
    transformation has been applied.

    Args:
        image (Union[sitk.Image, itk.Image]): The image to extract the properties from.
        **kwargs: Additional information.
    """

    def __init__(self,
                 image: Union[sitk.Image],
                 **kwargs):
        if isinstance(image, sitk.Image):
            image_ = image
        elif isinstance(image, itk.Image):
            image_ = convert_to_sitk_image(image)
        else:
            raise TypeError('Image must be of type SimpleITK.Image or itk.Image')

        self._spacing = image_.GetSpacing()
        self._origin = image_.GetOrigin()
        self._direction = image_.GetDirection()
        self._size = image_.GetSize()
        self.kwargs = kwargs

    def get_entry(self, key: str) -> Any:
        """Get entry from additional information.

        Args:
            key (str): Key of the entry.

        Returns:
            Any: The value of the entry or ``None`` if the key is not existing.
        """
        return self.kwargs.get(key, None)

    def set_entry(self, key: str, value: Any) -> None:
        """Set an entry as additional information.

        Args:
            key (str): Key of the entry.
            value (Any): Value of the entry.

        Returns:
            None
        """
        if key in self.kwargs.keys():
            raise ValueError(f'Key {key} already exists.')

        self.kwargs[key] = value

    @property
    def origin(self) -> Tuple[float, ...]:
        """Get the origin of the image.

        Returns:
            Tuple[float, ...]: The origin of the image.
        """
        return self._origin

    @property
    def spacing(self) -> Tuple[float, ...]:
        """Get the spacing of the image.

        Returns:
            Tuple[float, ...]: The spacing of the image.
        """
        return self._spacing

    @property
    def direction(self) -> Tuple[float, ...]:
        """Get the direction of the image.

        Returns:
            Tuple[float, ...]: The direction of the image.
        """
        return self._direction

    @property
    def size(self) -> Tuple[int, ...]:
        """Get the size of the image.

        Returns:
            Tuple[int, ...]: The size of the image.
        """
        return self._size

    def has_equal_origin_direction(self, other: 'ImageProperties') -> bool:
        """Check if the origin and direction of another :class:`ImageProperties` instance is equal.

        Args:
            other (ImageProperties): The other image properties.

        Returns:
            bool: True if the origin and direction are equal, False otherwise.
        """
        return (self._origin == other._origin and
                self._direction == other._direction)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ImageProperties):
            return False
        return (self._origin == other._origin and
                self._spacing == other._spacing and
                self._direction == other._direction and
                self._size == other._size)


class Image(ABC):
    """An abstract class to store images with additional attributes compared to :class:`SimpleITK.Image` and
    :class:`itk.Image`.

    In addition to standard image types, the :class:`Image` contains a :class:`~pyradise.data.taping.TransformTape`
    which is used to track and playback transformations applied to the image, such that the original physical
    properties (i.e. origin, direction, spacing) of the image can be retrieved.

    Args:
        image (Union[sitk.Image, itk.Image]): The image data to be stored.
    """

    def __init__(self,
                 image: Union[sitk.Image, itk.Image]
                 ) -> None:
        super().__init__()

        if isinstance(image, sitk.Image):
            self.image: itk.Image = convert_to_itk_image(image)

        else:
            self.image: itk.Image = image

        self.transform_tape = TransformTape()

    @staticmethod
    def _return_image_as(image: Union[sitk.Image, itk.Image],
                         as_sitk: bool
                         ) -> Union[sitk.Image, itk.Image]:
        """Return the image as either a :class:`SimpleITK.Image` or :class:`itk.Image`.

        Args:
            image (Union[sitk.Image, itk.Image]): The image to be returned.
            as_sitk (bool): If True, the image is returned as a :class:`SimpleITK.Image`, otherwise as a
             :class:`itk.Image`.

        Returns:
            Union[sitk.Image, itk.Image]: The image as either a :class:`SimpleITK.Image` or :class:`itk.Image`.
        """
        if isinstance(image, sitk.Image) and as_sitk:
            return image

        if isinstance(image, sitk.Image) and not as_sitk:
            return convert_to_itk_image(image)

        if isinstance(image, itk.Image) and as_sitk:
            return convert_to_sitk_image(image)

        return image

    @staticmethod
    def cast(image: Union[sitk.Image, itk.Image],
             pixel_type: Union[itk.support.types.itkCType, int],
             as_sitk: bool = False
             ) -> Union[sitk.Image, itk.Image]:
        """Cast an image to a certain pixel type and return it as either a :class:`itk.Image` or
        :class:`SimpleITK.Image`.

        Args:
            image (Union[sitk.Image, itk.Image]): The image to be casted.
            pixel_type (Union[itk.support.types.itkCType, int]): The output pixel type.
            as_sitk (bool): If True the image gets returned as a SimpleITK image otherwise as an ITK image.

        Returns:
            Union[sitk.Image, itk.Image]: The casted image as :class:`itk.Image` or :class:`SimpleITK.Image`.
        """
        if isinstance(image, sitk.Image):
            img = sitk.Cast(image, pixel_type)

        else:
            dimensions = itk.template(image)[1][1]
            input_image_type = itk.Image[itk.template(image)[1]]
            output_image_type = itk.Image[pixel_type, dimensions]

            caster = itk.CastImageFilter[input_image_type, output_image_type].New()
            caster.SetInput(image)
            caster.Update()
            img = caster.GetOutput()

        return Image._return_image_as(img, as_sitk)

    def get_image_data(self, as_sitk: bool = False) -> Union[itk.Image, sitk.Image]:
        """Get the image data as an :class:`itk.Image` or :class:`SimpleITK.Image` (with ``as_sitk=True``).

        Args:
            as_sitk (bool): If True returns the image as a SimpleITK image else as an ITK image.

        Returns:
            Union[itk.Image, sitk.Image]: The image as the either a :class:`itk.Image` or a :class:`SimpleITK.Image`.
        """
        if as_sitk:
            return convert_to_sitk_image(self.image)

        return self.image

    def set_image_data(self, image: Union[sitk.Image, itk.Image]) -> None:
        """Set the image data.

        Args:
            image (Union[sitk.Image, itk.Image]): The image to be set.

        Returns:
            None
        """
        if isinstance(image, sitk.Image):
            self.image = convert_to_itk_image(image)

        else:
            self.image = image

    def get_image_data_as_np(self) -> np.ndarray:
        """Get the image data as a numpy array.

        Returns:
            np.ndarray: The image data as a numpy array.
        """
        return itk.GetArrayFromImage(self.image)

    def get_image_itk_type(self) -> itk.Image:
        """Get the image type of this image.

        Returns:
            itk.Image: The image type of this image.
        """
        return itk.Image[itk.template(self.image)[1]]

    def get_origin(self) -> Tuple[float, ...]:
        """Get the origin of the image.

        Returns:
            Tuple[float, ...]: The origin of the image.
        """
        return tuple(self.image.GetOrigin())

    def get_direction(self) -> np.ndarray:
        """Get the direction of the image.

        Returns:
            np.ndarray: The direction of the image.
        """
        return itk.GetArrayFromMatrix(self.image.GetDirection())

    def get_spacing(self) -> Tuple[float, ...]:
        """Get the spacing of the image.

        Returns:
            Tuple[float, ...]: The spacing of the image
        """
        return tuple(self.image.GetSpacing())

    def get_size(self) -> Tuple[int, ...]:
        """Get the size of the image.

        Returns:
            Tuple[int, ...]: The size of the image.
        """
        return tuple(self.image.GetLargestPossibleRegion().GetSize())

    def get_dimensions(self) -> int:
        """Get the number of image dimensions.

        Returns:
            int: The number of image dimensions.
        """
        return itk.template(self.image)[1][1]

    def get_transform_tape(self) -> TransformTape:
        """Get the :class:`~pyradise.data.taping.TransformTape`.

        Returns:
            TransformTape: The :class:`~pyradise.data.taping.TransformTape`.
        """
        return self.transform_tape

    def set_transform_tape(self, tape: TransformTape) -> None:
        """Set the :class:`~pyradise.data.taping.TransformTape`.

        Args:
            tape (TransformTape): The :class:`~pyradise.data.taping.TransformTape`.

        Returns:
            None
        """
        self.transform_tape = tape

    def add_transform_info(self, info: TransformInfo) -> None:
        """Add a :class:`~pyradise.data.taping.TransformInfo` instance to the
        :class:`~pyradise.data.taping.TransformTape` instance of the image.

        Args:
            info (TransformInfo): The :class:`~pyradise.data.taping.TransformInfo` instance to be added.

        Returns:
            None
        """
        self.transform_tape.record(info)

    @abstractmethod
    def copy_info(self,
                  source: 'Image',
                  include_transforms: bool = False
                  ) -> None:
        """Copy the image information from another image.

        Args:
            source (Image): The image to copy the information from.
            include_transforms (bool): If True the :class:`~pyradise.data.taping.TransformTape` is copied,
             otherwise not.

        Returns:
            None
        """
        raise NotImplementedError()

    @abstractmethod
    def is_intensity_image(self) -> bool:
        """Return True if the image is an intensity image otherwise False.

        Returns:
            bool: n/a
        """
        raise NotImplementedError()

    @abstractmethod
    def __eq__(self, other: object):
        """Check if the provided instance is of the same type and if it has the same identification.

        Args:
            other (object): The object to be checked.

        Returns:
            bool: True if the object is an image and possess the same identification.
        """
        raise NotImplementedError()


class IntensityImage(Image):
    """An intensity image class including a :class:`~pyradise.data.taping.TransformTape` and
    :class:`~pyradise.data.modality.Modality` to identify the imaging modality of the image.

    Args:
        image (Union[sitk.Image, itk.Image]): The image data as :class:`itk.Image` or :class:`SimpleITK.Image`.
        modality (Modality): The image :class:`~pyradise.data.modality.Modality`.
    """

    def __init__(self,
                 image: Union[sitk.Image, itk.Image],
                 modality: Modality
                 ) -> None:
        super().__init__(image)

        self.modality = modality

    def get_modality(self,
                     as_str: bool = False
                     ) -> Union[Modality, str]:
        """Get the :class:`~pyradise.data.modality.Modality`.

        Args:
            as_str (bool): If True returns the :class:`~pyradise.data.modality.Modality` as a string, otherwise as
             type :class:`~pyradise.data.modality.Modality`.

        Returns:
            Union[Modality, str]: The :class:`~pyradise.data.modality.Modality`.
        """
        if as_str:
            return self.modality.get_name()

        return self.modality

    def set_modality(self, modality: Modality) -> None:
        """Set the :class:`~pyradise.data.modality.Modality`.

        Args:
            modality (Modality): The :class:`~pyradise.data.modality.Modality`.

        Returns:
            None
        """
        self.modality = modality

    def copy_info(self,
                  source: 'IntensityImage',
                  include_transforms: bool = False
                  ) -> None:
        """Copy the image information from another :class:`IntensityImage`.

        The copied information includes the following attributes:

            - :class:`~pyradise.data.modality.Modality`
            - :class:`~pyradise.data.taping.TransformTape` (optional)

        Raises:
            ValueError: If the source image is not an instance of :class:`IntensityImage`.

        Args:
            source (IntensityImage): The source image.
            include_transforms (bool): If True the :class:`~pyradise.data.taping.TransformTape` is copied,
             otherwise not.

        Returns:
            None
        """
        if not isinstance(source, IntensityImage):
            raise TypeError('The source image must be an instance of IntensityImage.')

        self.modality = deepcopy(source.get_modality())

        if include_transforms:
            self.transform_tape = deepcopy(source.get_transform_tape())

    def is_intensity_image(self) -> bool:
        """If the image is an instance of :class:`IntensityImage` this function returns True otherwise False.

        Returns:
            bool: True
        """
        return True

    def __eq__(self, other: object) -> bool:
        """Check if the provided instance is of the same type and if it has the same
        :class:`~pyradise.data.modality.Modality`.

        Args:
            other (object): The object to be checked.

        Returns:
            bool: True if the object is an :class:`IntensityImage` and possess the same identification.

        """
        if not isinstance(other, IntensityImage):
            return False

        return self.modality == other.modality

    def __str__(self) -> str:
        return f'Intensity image: {self.modality.name}'


class SegmentationImage(Image):
    """A segmentation image class including a :class:`~pyradise.data.taping.TransformTape` and additional attributes
    to identify the :class:`~pyradise.data.organ.Organ` segmented and the :class:`~pyradise.data.rater.Rater` who
    created the segmentation.

    The specification of :class:`~pyradise.data.rater.Rater` is optional and can be omitted if not explicitly used.

    Args:
        image (Union[sitk.Image, itk.Image]): The segmentation image data.
        organ (Organ): The :class:`~pyradise.data.organ.Organ` represented by the segmentation image.
        rater (Optional[Rater]): The :class:`~pyradise.data.rater.Rater` of the segmentation image (default: None).
    """

    def __init__(self,
                 image: Union[sitk.Image, itk.Image],
                 organ: Organ,
                 rater: Optional[Rater] = Rater.get_default()
                 ) -> None:
        super().__init__(image)
        self.organ: Organ = organ
        self.rater: Rater = rater

    def get_organ(self,
                  as_str: bool = False
                  ) -> Union[Organ, str]:
        """Get the :class:`~pyradise.data.organ.Organ`.

        Args:
            as_str (bool): It True the :class:`~pyradise.data.organ.Organ` gets returned as a :class:`str`,
             otherwise as an :class:`~pyradise.data.organ.Organ`.

        Returns:
            Union[Organ, str]: The :class:`~pyradise.data.organ.Organ`.
        """
        if as_str:
            return self.organ.name

        return self.organ

    def set_organ(self, organ: Organ) -> None:
        """Set the :class:`~pyradise.data.organ.Organ`.

        Args:
            organ (Organ): The :class:`~pyradise.data.organ.Organ`.

        Returns:
            None
        """
        self.organ = organ

    def get_rater(self) -> Rater:
        """Get the :class:`~pyradise.data.rater.Rater`.

        Returns:
            Rater: The :class:`~pyradise.data.rater.Rater`.
        """
        return self.rater

    def set_rater(self, rater: Rater) -> None:
        """Set the :class:`~pyradise.data.rater.Rater`.

        Args:
            rater (Rater): The :class:`~pyradise.data.rater.Rater`.

        Returns:
            None
        """
        self.rater: Rater = rater

    def get_organ_rater_combination(self) -> OrganRaterCombination:
        """Get the :class:`~pyradise.data.organ.OrganRaterCombination`.

        Returns:
            OrganRaterCombination: The combination of the :class:`~pyradise.data.organ.Organ` and the
            :class:`~pyradise.data.rater.Rater`.
        """
        return OrganRaterCombination(self.organ, self.rater)

    def set_organ_rater_combination(self, organ_rater_combination: OrganRaterCombination) -> None:
        """Set the :class:`~pyradise.data.organ.OrganRaterCombination`.

        Args:
            organ_rater_combination (OrganRaterCombination): The :class:`~pyradise.data.organ.OrganRaterCombination`.

        Returns:
            None
        """
        self.organ: Organ = organ_rater_combination.organ
        self.rater: Rater = organ_rater_combination.rater

    def copy_info(self,
                  source: 'SegmentationImage',
                  include_transforms: bool = False
                  ) -> None:
        """Copy the image information from another :class:`SegmentationImage`.

        The copied information includes the following attributes:

            - :class:`~pyradise.data.organ.Organ`
            - :class:`~pyradise.data.rater.Rater`
            - :class:`~pyradise.data.taping.TransformTape` (optional)

        Raises:
            ValueError: If the source image is not an instance of :class:`SegmentationImage`.

        Args:
            source (IntensityImage): The source image.
            include_transforms (bool): If True the :class:`~pyradise.data.taping.TransformTape` is copied, otherwise
             not.

        Returns:
            None
        """
        if not isinstance(source, SegmentationImage):
            raise TypeError('The source image must be an instance of SegmentationImage.')

        self.organ: Organ = deepcopy(source.get_organ())
        self.rater: Rater = deepcopy(source.get_rater())

        if include_transforms:
            self.transform_tape = deepcopy(source.get_transform_tape())

    def is_intensity_image(self) -> bool:
        """If the image is an :class:`IntensityImage` this function returns True, otherwise False.

        Returns:
            bool: False
        """
        return False

    def is_binary(self) -> bool:
        """Check if the image is binary.

        Returns:
            bool: True if the image is binary, otherwise False.
        """
        image_np = itk.GetArrayViewFromImage(self.image)
        unique_pixel_vals = np.unique(image_np)

        if unique_pixel_vals.shape[0] == 2 and unique_pixel_vals[0] == 0:
            return True

        return False

    def __eq__(self, other) -> bool:
        """Check if the provided instance is of the same type and if it has the same :class:`~pyradise.data.organ.Organ`
         and :class:`~pyradise.rater.Rater`.

        Args:
            other (object): The object to be checked.

        Returns:
            bool: True if the object is an :class:`SegmentationImage` and possess the same identification.
        """
        if not isinstance(other, SegmentationImage):
            return False

        return all((self.organ == other.organ, self.rater == other.rater))

    def __str__(self) -> str:
        if not self.rater:
            return f'SegmentationImage: {self.organ.name}'

        return f'SegmentationImage: {self.organ.name} / {self.rater.name}'
